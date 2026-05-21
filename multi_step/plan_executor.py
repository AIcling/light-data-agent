from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from analysis.result_summarizer import ResultSummarizer
from core.config import AppConfig
from core.types import TableSchema
from memory.memory_store import MemoryStore
from multi_step.final_synthesizer import FinalSynthesizer
from multi_step.goal_decomposer import GoalDecomposer
from multi_step.multi_step_plan import MultiStepAnalysisPlan, PlanStep
from multi_step.plan_generator import PlanGenerator
from multi_step.plan_validator import PlanValidator
from multi_step.result_critic import ResultCritic
from multi_step.step_executor import StepExecutor
from multi_step.step_observer import StepObserver
from sql_layer.executor import QueryEngine
from sql_layer.generator import SQLGenerator
from sql_layer.repair import SQLRepairer
from sql_layer.validator import SQLValidator
from visualization.chart_recommender import ChartRecommender


@dataclass
class PlanExecutor:
    config: AppConfig
    query_engine: QueryEngine
    sql_generator: SQLGenerator
    sql_validator: SQLValidator
    sql_repairer: SQLRepairer
    memory: MemoryStore
    goal_decomposer: GoalDecomposer = field(default_factory=GoalDecomposer)
    plan_generator: PlanGenerator = field(default_factory=PlanGenerator)
    plan_validator: PlanValidator = field(default_factory=PlanValidator)
    step_executor: StepExecutor | None = None
    step_observer: StepObserver = field(default_factory=StepObserver)
    result_critic: ResultCritic = field(default_factory=ResultCritic)
    final_synthesizer: FinalSynthesizer = field(default_factory=FinalSynthesizer)
    result_summarizer: ResultSummarizer = field(default_factory=ResultSummarizer)
    chart_recommender: ChartRecommender = field(default_factory=ChartRecommender)

    def __post_init__(self) -> None:
        if self.step_executor is None:
            self.step_executor = StepExecutor(sql_generator=self.sql_generator)

    def should_use_multi_step(self, question: str, resolved_query: str, schema: TableSchema) -> dict:
        if not self.config.enable_multi_step_plan:
            return {"requires_multi_step": False}
        return self.goal_decomposer.decompose(question, resolved_query, schema, self.memory)

    def build_plan(
        self,
        question: str,
        resolved_query: str,
        schema: TableSchema,
        decomposition: dict,
    ) -> MultiStepAnalysisPlan:
        return self.plan_generator.generate(
            decomposition,
            question,
            schema,
            self.memory.project_id,
            self.memory.dataset_id or schema.dataset_id,
        )

    def execute(
        self,
        plan: MultiStepAnalysisPlan,
        schema: TableSchema,
        raw_df: pd.DataFrame | None,
        workspace=None,
    ) -> dict[str, Any]:
        validation = self.plan_validator.validate(plan)
        if not validation["valid"]:
            return {"status": "error", "errors": validation["errors"], "plan": plan.to_dict()}

        step_outputs: dict[str, Any] = {}
        ordered = self._topological_sort(plan.steps)
        last_df: pd.DataFrame | None = None
        last_sql = ""
        critical_failed = False

        for step in ordered:
            if critical_failed and step.step_type not in {"synthesis", "report_generation"}:
                step.status = "skipped"
                continue

            step.status = "running"
            if not self._dependencies_ready(step, plan.steps):
                step.status = "skipped"
                step.warnings.append("Dependencies not satisfied.")
                continue

            result = self.step_executor.execute_step(step, schema, raw_df, step_outputs, self.memory)
            if result.get("status") == "failed":
                step.status = "failed"
                step.warnings.append(result.get("error", "Step failed"))
                if step.step_type in {"sql_query", "contribution_decomposition"}:
                    critical_failed = True
                continue

            if result.get("skip_sql"):
                step.result_summary = result.get("result_summary", {})
                step.status = "success"
                if step.output_key:
                    step_outputs[step.output_key] = step.result_summary
                self.step_observer.observe(step, step.result_summary, extra=result.get("extra"))
                self.result_critic.critique(step, step.result_summary)
                continue

            sql = result["sql_candidate"].sql
            validation_result = self.sql_validator.validate(sql, schema, result.get("analysis_plan"))
            sql_to_run = validation_result.normalized_sql or sql

            repair_attempts = 0
            while not validation_result.valid and repair_attempts < self.config.max_sql_repair_attempts:
                repair_attempts += 1
                repaired = self.sql_repairer.repair_with_result(
                    result["question"], sql_to_run, validation_result.errors, schema, result.get("analysis_plan"), repair_attempts
                )
                sql_to_run = repaired.sql
                validation_result = self.sql_validator.validate(sql_to_run, schema, result.get("analysis_plan"))

            if not validation_result.valid:
                step.status = "failed"
                step.warnings.extend(validation_result.errors)
                critical_failed = True
                continue

            execution = self.query_engine.execute(sql_to_run)
            if execution.status != "success":
                step.status = "failed"
                step.warnings.append(execution.error or "Execution failed")
                critical_failed = True
                continue

            step.sql = sql_to_run
            last_sql = sql_to_run
            last_df = execution.dataframe
            summary = self.result_summarizer.summarize(execution.dataframe)
            step.result_summary = summary
            step.chart_spec = self.chart_recommender.recommend(
                result["intent"], execution.dataframe, summary, result.get("analysis_plan")
            )
            step.status = "success"
            if step.output_key:
                step_outputs[step.output_key] = {"summary": summary, "sql": sql_to_run}

            self.step_observer.observe(step, summary, execution.dataframe, result.get("extra"))
            self.result_critic.critique(step, summary, execution.dataframe)

            if workspace and self.memory.project_id:
                workspace.artifact_store.save_sql_artifact(
                    self.memory.project_id,
                    sql_to_run,
                    f"{plan.plan_id}_{step.step_id}.sql",
                    metadata={"step_id": step.step_id, "plan_id": plan.plan_id},
                )

        synthesis = self.final_synthesizer.synthesize(plan, step_outputs)
        plan.status = "completed" if not critical_failed else "partial"

        analysis_record = None
        if workspace and self.memory.project_id:
            analysis_record = workspace.save_analysis_record(
                project_id=self.memory.project_id,
                user_query=plan.goal,
                resolved_query=plan.goal,
                task_type=plan.plan_type,
                status=plan.status,
                dataset_id=self.memory.dataset_id,
                goal=plan.goal,
                main_findings=synthesis.get("findings", []),
                limitations=synthesis.get("limitations", []),
            )
            self._persist_steps(workspace, plan, analysis_record.analysis_id)

        return {
            "status": "success" if not critical_failed else "partial",
            "plan": plan.to_dict(),
            "synthesis": synthesis,
            "step_outputs": step_outputs,
            "sql": last_sql,
            "result": last_df,
            "explanation": synthesis.get("explanation", ""),
            "findings": synthesis.get("findings", []),
            "limitations": synthesis.get("limitations", []),
            "analysis_id": analysis_record.analysis_id if analysis_record else "",
        }

    def _persist_steps(self, workspace, plan: MultiStepAnalysisPlan, analysis_id: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with workspace.store.connect() as conn:
            for order, step in enumerate(plan.steps):
                conn.execute(
                    """
                    INSERT INTO analysis_steps (
                        step_id, analysis_id, step_order, step_type, goal, depends_on_json,
                        status, sql, result_summary_json, observations_json, warnings_json,
                        artifacts_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        step.step_id,
                        analysis_id,
                        order,
                        step.step_type,
                        step.goal,
                        json.dumps(step.depends_on),
                        step.status,
                        step.sql,
                        json.dumps(step.result_summary, ensure_ascii=False, default=str),
                        json.dumps(step.observations, ensure_ascii=False),
                        json.dumps(step.warnings, ensure_ascii=False),
                        json.dumps(step.artifacts, ensure_ascii=False),
                        now,
                        now,
                    ),
                )

    def _topological_sort(self, steps: list[PlanStep]) -> list[PlanStep]:
        step_map = {s.step_id: s for s in steps}
        visited: set[str] = set()
        result: list[PlanStep] = []

        def visit(step_id: str) -> None:
            if step_id in visited:
                return
            visited.add(step_id)
            step = step_map.get(step_id)
            if not step:
                return
            for dep in step.depends_on:
                visit(dep)
            result.append(step)

        for step in steps:
            visit(step.step_id)
        return result

    def _dependencies_ready(self, step: PlanStep, all_steps: list[PlanStep]) -> bool:
        status_map = {s.step_id: s.status for s in all_steps}
        for dep in step.depends_on:
            if status_map.get(dep) not in {"success", "skipped"}:
                return False
        return True
