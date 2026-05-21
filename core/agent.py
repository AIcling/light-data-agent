from __future__ import annotations

from dataclasses import dataclass
from typing import Union

from analysis.explainer import ResultExplainer
from analysis.result_summarizer import ResultSummarizer
from core.config import AppConfig
from core.types import AgentResponse, TableSchema
from core.workflow import WorkflowController
from llm.client import LLMClient
from memory.memory_resolver import MemoryResolver
from memory.memory_store import MemoryStore
from memory.session_memory import SessionMemory
from multi_step.plan_executor import PlanExecutor
from sql_layer.executor import QueryEngine
from sql_layer.generator import SQLGenerator
from sql_layer.repair import SQLRepairer
from sql_layer.validator import SQLValidator
from visualization.chart_recommender import ChartRecommender


@dataclass
class DataAgent:
    config: AppConfig
    query_engine: QueryEngine
    memory: Union[MemoryStore, SessionMemory]
    workspace=None
    workflow: WorkflowController | None = None
    plan_executor: PlanExecutor | None = None

    def __post_init__(self) -> None:
        if isinstance(self.memory, SessionMemory):
            store = MemoryStore()
            store.session = self.memory
            self.memory = store
        if self.workspace and self.config.enable_persistent_memory:
            project_id = getattr(self.workspace, "_current_project_id", None)
            if project_id:
                self.memory.attach_workspace(self.workspace, project_id)
        llm_client = LLMClient(self.config)
        sql_generator = SQLGenerator(llm_client=llm_client, max_result_rows=self.config.max_result_rows)
        sql_validator = SQLValidator(
            query_engine=self.query_engine,
            max_result_rows=self.config.max_result_rows,
            allow_write_sql=self.config.allow_write_sql,
        )
        sql_repairer = SQLRepairer()
        if self.workflow is None:
            self.workflow = WorkflowController(
                config=self.config,
                query_engine=self.query_engine,
                memory=self.memory,
                sql_generator=sql_generator,
                sql_validator=sql_validator,
                sql_repairer=sql_repairer,
                result_summarizer=ResultSummarizer(),
                result_explainer=ResultExplainer(),
                chart_recommender=ChartRecommender(),
            )
        if self.plan_executor is None:
            self.plan_executor = PlanExecutor(
                config=self.config,
                query_engine=self.query_engine,
                sql_generator=sql_generator,
                sql_validator=sql_validator,
                sql_repairer=sql_repairer,
                memory=self.memory,
            )

    def answer(self, question: str, schema: TableSchema, raw_df=None) -> AgentResponse:
        resolver = MemoryResolver()
        resolution = resolver.resolve(question, self.memory)
        if resolution.get("needs_clarification") and resolution.get("confidence", 1) < self.config.memory_confidence_threshold:
            return AgentResponse(
                status="clarification",
                question=question,
                resolved_query=resolution.get("resolved_query", question),
                needs_clarification=resolution["needs_clarification"],
                errors=[resolution["needs_clarification"].get("message", "Need clarification")],
            )

        resolved = resolution.get("resolved_query", question)
        decomposition = self.plan_executor.should_use_multi_step(question, resolved, schema)
        if decomposition.get("requires_multi_step"):
            plan = self.plan_executor.build_plan(question, resolved, schema, decomposition)
            result = self.plan_executor.execute(plan, schema, raw_df, self.workspace)
            return AgentResponse(
                status=result.get("status", "success"),
                question=question,
                resolved_query=resolved,
                sql=result.get("sql", ""),
                result=result.get("result"),
                explanation=result.get("explanation", ""),
                multi_step=True,
                multi_step_plan=result.get("plan"),
                insights=result.get("findings", []),
                limitations=result.get("limitations", []),
                analysis_id=result.get("analysis_id", ""),
                debug={"step_outputs": result.get("step_outputs", {})},
            )

        state = self.workflow.run(question, schema, raw_df)
        response = self.workflow.to_agent_response(state)
        if self.workspace and self.memory.project_id and response.status == "success":
            record = self.workspace.save_analysis_record(
                project_id=self.memory.project_id,
                user_query=question,
                resolved_query=response.resolved_query or question,
                task_type=response.intent.task_type if response.intent else "",
                status="success",
                dataset_id=self.memory.dataset_id,
                goal=response.analysis_plan.goal if response.analysis_plan else question,
                main_findings=response.insights,
                limitations=response.limitations,
            )
            response.analysis_id = record.analysis_id
            if response.sql:
                self.workspace.artifact_store.save_sql_artifact(
                    self.memory.project_id,
                    response.sql,
                    f"{record.analysis_id}.sql",
                    analysis_id=record.analysis_id,
                )
            if response.chart_spec:
                self.workspace.artifact_store.save_chart_spec(
                    self.memory.project_id,
                    response.chart_spec,
                    f"{record.analysis_id}_chart.json",
                    analysis_id=record.analysis_id,
                )
        return response

    def set_project(self, project_id: str) -> None:
        if self.workspace:
            self.memory.attach_workspace(self.workspace, project_id)
            self.workspace._current_project_id = project_id
