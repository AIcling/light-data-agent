from __future__ import annotations

import time
from dataclasses import dataclass, field

import pandas as pd

from analysis.explainer import ResultExplainer
from analysis.result_summarizer import ResultSummarizer
from core.config import AppConfig
from core.state import AgentState, new_run_id, new_session_id
from core.trace import TraceLogger, workflow_status_labels
from core.types import AgentResponse, TableSchema
from memory.memory_resolver import MemoryResolver
from memory.memory_store import MemoryStore
from observation.contribution_analysis import ContributionAnalyzer
from observation.data_quality import DataQualityAnalyzer
from observation.insight_generator import InsightGenerator
from planning.followup_planner import FollowUpPlanner
from planning.task_planner import TaskPlanner
from reporting.markdown_report import ReportBuilder
from safety.masking import mask_sensitive_dataframe
from safety.prompt_guard import PromptGuard
from safety.sensitive_detector import SensitiveColumnDetector
from schema_grounding.cannot_answer import CannotAnswerDetector
from schema_grounding.field_selector import RelevantFieldSelector
from schema_grounding.schema_context import SchemaContextBuilder
from sql_layer.generator import SQLGenerator
from sql_layer.repair import SQLRepairer
from sql_layer.validator import SQLValidator
from sql_layer.executor import QueryEngine
from visualization.chart_recommender import ChartRecommender


@dataclass
class WorkflowController:
    config: AppConfig
    query_engine: QueryEngine
    memory: MemoryStore
    sql_generator: SQLGenerator
    sql_validator: SQLValidator
    sql_repairer: SQLRepairer
    task_planner: TaskPlanner = field(default_factory=TaskPlanner)
    memory_resolver: MemoryResolver = field(default_factory=MemoryResolver)
    field_selector: RelevantFieldSelector = field(default_factory=RelevantFieldSelector)
    schema_context_builder: SchemaContextBuilder = field(default_factory=SchemaContextBuilder)
    cannot_answer_detector: CannotAnswerDetector = field(default_factory=CannotAnswerDetector)
    result_summarizer: ResultSummarizer = field(default_factory=ResultSummarizer)
    result_explainer: ResultExplainer = field(default_factory=ResultExplainer)
    chart_recommender: ChartRecommender = field(default_factory=ChartRecommender)
    data_quality_analyzer: DataQualityAnalyzer = field(default_factory=DataQualityAnalyzer)
    contribution_analyzer: ContributionAnalyzer = field(default_factory=ContributionAnalyzer)
    insight_generator: InsightGenerator = field(default_factory=InsightGenerator)
    followup_planner: FollowUpPlanner = field(default_factory=FollowUpPlanner)
    prompt_guard: PromptGuard = field(default_factory=PromptGuard)
    sensitive_detector: SensitiveColumnDetector = field(default_factory=SensitiveColumnDetector)
    trace_logger: TraceLogger = field(default_factory=TraceLogger)

    def run(self, question: str, schema: TableSchema, raw_df: pd.DataFrame | None = None) -> AgentState:
        state = AgentState(
            run_id=new_run_id(),
            session_id=self.memory.session.session_id or new_session_id(),
            user_query=question.strip(),
        )
        self.memory.session.session_id = state.session_id
        self.memory.bind_dataset(schema)

        guard = self.prompt_guard.check(question)
        if guard.get("blocked"):
            state.add_error("prompt_guard", "Query blocked by safety policy.", guard)
            state.status = "FAILED_SAFE"
            return state

        # Step 1: Resolve context from memory
        t0 = time.perf_counter()
        resolution = self.memory_resolver.resolve(question, self.memory)
        state.resolved_query = resolution["resolved_query"]
        state.resolution_type = resolution["resolution_type"]
        state.normalized_query = question.strip()
        state.dataset_id = schema.dataset_id or schema.table_name
        state.table_names = [schema.table_name]
        state.schema = schema
        state.add_trace(
            "CONTEXT_RESOLVED",
            "success",
            {"question": question},
            resolution,
            duration_ms=int((time.perf_counter() - t0) * 1000),
        )

        # Step 2: Schema grounding
        t0 = time.perf_counter()
        relevant_fields = self.field_selector.select(state.resolved_query, schema, self.memory)
        state.relevant_fields = relevant_fields
        state.schema_context = self.schema_context_builder.build(schema, relevant_fields)
        state.add_trace(
            "SCHEMA_GROUNDED",
            "success",
            {"table": schema.table_name},
            {"relevant_columns": len(relevant_fields.get("relevant_columns", []))},
            duration_ms=int((time.perf_counter() - t0) * 1000),
        )

        # Step 3: Plan + intent
        t0 = time.perf_counter()
        derived = resolution["resolution_type"] == "follow_up"
        intent, analysis_plan, plan_cannot = self.task_planner.plan(
            state.resolved_query, schema, self.memory, derived_from_memory=derived
        )
        state.intent = intent
        state.analysis_plan = analysis_plan

        cannot = plan_cannot or self.cannot_answer_detector.detect(
            state.resolved_query, schema, intent.task_type
        )
        if cannot and intent.task_type not in {
            "data_quality", "contribution_analysis", "report_generation", "lookup"
        }:
            state.cannot_answer = cannot
            state.status = "CANNOT_ANSWER"
            state.add_trace("CANNOT_ANSWER_DETECTED", "warning", {}, cannot)
            self.memory.record_failure(question, cannot.get("reason", ""))
            self.trace_logger.log_run(state)
            return state

        state.add_trace(
            "INTENT_PARSED",
            "success",
            {"query": state.resolved_query},
            intent.to_dict(),
            duration_ms=int((time.perf_counter() - t0) * 1000),
        )
        state.add_trace("PLAN_CREATED", "success", {}, analysis_plan.to_dict())

        # Report generation short-circuit
        if intent.task_type == "report_generation":
            report = ReportBuilder().build(self.memory, schema.table_name)
            state.explanation = report
            state.status = "COMPLETED"
            state.add_trace("EXPLAINED", "success", {}, {"type": "report"})
            return state

        # Step 4: SQL generation
        t0 = time.perf_counter()
        candidate = self.sql_generator.generate(
            state.resolved_query, schema, intent, self.memory.session, analysis_plan
        )
        state.sql_candidate = candidate
        state.add_trace("SQL_GENERATED", "success", {}, candidate.to_dict(), duration_ms=int((time.perf_counter() - t0) * 1000))

        if candidate.cannot_answer:
            state.status = "CANNOT_ANSWER"
            state.cannot_answer = {
                "cannot_answer": True,
                "reason": candidate.error_message or candidate.reasoning,
                "available_alternatives": [],
            }
            self.memory.record_failure(question, candidate.error_message or "")
            self.trace_logger.log_run(state)
            return state

        # Step 5: Validation + repair
        sql_to_execute = candidate.sql
        validation = self.sql_validator.validate(sql_to_execute, schema, analysis_plan)
        state.sql_validation = validation
        sql_to_execute = validation.normalized_sql or sql_to_execute

        while not validation.valid and state.repair_attempts < self.config.max_sql_repair_attempts:
            state.repair_attempts += 1
            repair_result = self.sql_repairer.repair_with_result(
                state.resolved_query,
                sql_to_execute,
                validation.errors,
                schema,
                analysis_plan,
                state.repair_attempts,
            )
            state.repaired_sql_candidate = repair_result.to_dict()
            state.add_trace(
                "SQL_REPAIR_ATTEMPTED",
                "success" if repair_result.repaired else "failed",
                {"attempt": state.repair_attempts},
                repair_result.to_dict(),
            )
            sql_to_execute = repair_result.sql
            validation = self.sql_validator.validate(sql_to_execute, schema, analysis_plan)
            state.sql_validation = validation
            sql_to_execute = validation.normalized_sql or sql_to_execute

        if not validation.valid:
            state.add_trace("SQL_VALIDATED", "failed", {}, validation.to_dict())
            state.add_error("sql_validation", "; ".join(validation.errors))
            state.status = "FAILED_SAFE"
            self.memory.record_failure(question, "; ".join(validation.errors))
            self.trace_logger.log_run(state)
            return state

        state.add_trace("SQL_VALIDATED", "success", {}, validation.to_dict())
        state.final_sql = sql_to_execute

        # Step 6: Execute
        t0 = time.perf_counter()
        execution = self.query_engine.execute(sql_to_execute)
        state.execution_result = execution
        if execution.status != "success":
            state.add_trace("EXECUTED", "failed", {}, execution.to_dict(), duration_ms=int((time.perf_counter() - t0) * 1000))
            state.add_error("sql_execution", execution.error or "Execution failed")
            state.status = "FAILED_SAFE"
            self.memory.record_failure(question, execution.error or "")
            self.trace_logger.log_run(state)
            return state

        result_df = execution.dataframe
        if self.config.mask_sensitive_columns:
            sensitive = self.sensitive_detector.detect(schema.column_names)
            result_df = mask_sensitive_dataframe(result_df, sensitive)

        state.result_df = result_df
        state.add_trace("EXECUTED", "success", {}, {"row_count": execution.row_count}, duration_ms=int((time.perf_counter() - t0) * 1000))

        # Step 7: Observe
        t0 = time.perf_counter()
        result_summary = self.result_summarizer.summarize(result_df)
        state.result_summary = result_summary

        quality_result = None
        if intent.task_type == "data_quality" and raw_df is not None:
            quality_result = self.data_quality_analyzer.analyze(raw_df, schema.to_dict())
            result_summary["data_quality"] = quality_result

        contribution_result = None
        if intent.task_type == "contribution_analysis" and raw_df is not None:
            contribution_result = self.contribution_analyzer.analyze(
                raw_df,
                schema.to_dict(),
                metric=intent.metric_candidates[0] if intent.metric_candidates else None,
                dimension=intent.dimension_candidates[0] if intent.dimension_candidates else None,
                time_column=intent.time_column_candidates[0] if intent.time_column_candidates else None,
            )
            result_summary["contribution"] = contribution_result

        insights, limitations = self.insight_generator.generate(
            result_summary, intent.task_type, contribution_result, quality_result
        )
        state.insights = insights
        state.limitations = limitations
        state.add_trace("OBSERVED", "success", {}, {"insights": len(insights)}, duration_ms=int((time.perf_counter() - t0) * 1000))

        # Step 8: Explain + chart
        explanation_structured = self.result_explainer.explain_structured(
            question,
            sql_to_execute,
            result_summary,
            intent,
            analysis_plan,
            insights,
            limitations,
            contribution_result,
        )
        state.explanation_structured = explanation_structured
        state.explanation = self.result_explainer.explain(
            question,
            sql_to_execute,
            result_summary,
            intent,
            analysis_plan,
            insights,
            limitations,
            contribution_result,
        )
        state.chart_spec = self.chart_recommender.recommend(intent, result_df, result_summary, analysis_plan)
        state.follow_up_suggestions = self.followup_planner.suggest(intent.task_type, schema.to_dict())
        state.add_trace("EXPLAINED", "success", {}, {"chart": state.chart_spec is not None})

        # Step 9: Update memory
        self.memory.record_success(
            question=question,
            resolved_query=state.resolved_query or question,
            intent=intent,
            sql=sql_to_execute,
            result_summary=result_summary,
            chart_spec=state.chart_spec,
            insights=insights,
            limitations=limitations,
            follow_up_suggestions=state.follow_up_suggestions,
        )
        if self.memory.analysis and state.explanation:
            if self.memory.analysis.steps:
                self.memory.analysis.steps[-1]["explanation"] = state.explanation
        state.memory_snapshot = self.memory.to_dict()
        state.add_trace("MEMORY_UPDATED", "success", {}, {"queries": len(self.memory.queries)})
        state.status = "COMPLETED"
        self.trace_logger.log_run(state)
        return state

    def to_agent_response(self, state: AgentState) -> AgentResponse:
        if state.cannot_answer and state.status == "CANNOT_ANSWER":
            return AgentResponse(
                status="error",
                question=state.user_query,
                resolved_query=state.resolved_query or "",
                intent=state.intent,
                analysis_plan=state.analysis_plan,
                stage="cannot_answer",
                errors=[state.cannot_answer.get("reason", "Cannot answer.")],
                cannot_answer=state.cannot_answer,
                trace=[e.to_dict() for e in state.trace],
                workflow_status=workflow_status_labels(state),
                run_id=state.run_id,
                debug=state.to_dict(),
            )

        if state.errors:
            return AgentResponse(
                status="error",
                question=state.user_query,
                resolved_query=state.resolved_query or "",
                intent=state.intent,
                analysis_plan=state.analysis_plan,
                sql=state.final_sql,
                validation=state.sql_validation,
                stage=state.errors[-1].get("stage"),
                errors=[e.get("message", "") for e in state.errors],
                trace=[e.to_dict() for e in state.trace],
                workflow_status=workflow_status_labels(state),
                run_id=state.run_id,
                debug=state.to_dict(),
            )

        return AgentResponse(
            status="success",
            question=state.user_query,
            resolved_query=state.resolved_query or "",
            intent=state.intent,
            analysis_plan=state.analysis_plan,
            sql=state.final_sql,
            validation=state.sql_validation,
            result=state.result_df,
            result_summary=state.result_summary or {},
            explanation=state.explanation,
            explanation_structured=state.explanation_structured,
            chart_spec=state.chart_spec,
            follow_up_suggestions=state.follow_up_suggestions,
            insights=state.insights,
            limitations=state.limitations,
            trace=[e.to_dict() for e in state.trace],
            workflow_status=workflow_status_labels(state),
            run_id=state.run_id,
            debug=state.to_dict(),
        )
