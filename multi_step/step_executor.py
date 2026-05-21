from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from core.types import IntentResult, TableSchema
from observation.contribution_analysis import ContributionAnalyzer
from observation.data_quality import DataQualityAnalyzer
from planning.intent_parser import RuleBasedIntentParser
from planning.task_planner import TaskPlanner
from sql_layer.generator import SQLGenerator


STEP_QUESTIONS = {
    "monthly_compare": "每个月销售额是多少？",
    "region_contribution": "各地区销售额是多少？",
    "category_contribution": "不同产品类别的销售额是多少？",
    "metric_summary": "总销售额是多少？",
    "dimension_compare": "各地区销售额是多少？",
    "trend_summary": "每个月销售额趋势是什么？",
    "preview": "显示数据明细",
    "top_dimension": "销售额最高的前5个类别是什么？",
}


@dataclass
class StepExecutor:
    sql_generator: SQLGenerator
    task_planner: TaskPlanner | None = None
    data_quality: DataQualityAnalyzer | None = None
    contribution: ContributionAnalyzer | None = None

    def __post_init__(self) -> None:
        self.task_planner = self.task_planner or TaskPlanner()
        self.data_quality = self.data_quality or DataQualityAnalyzer()
        self.contribution = self.contribution or ContributionAnalyzer()

    def execute_step(
        self,
        step,
        schema: TableSchema,
        raw_df: pd.DataFrame | None,
        previous_outputs: dict[str, Any],
        memory,
    ) -> dict[str, Any]:
        if step.step_type == "data_quality_check":
            return self._quality_step(step, raw_df, schema)
        if step.step_type == "contribution_decomposition":
            return self._contribution_step(step, raw_df, schema, previous_outputs)
        if step.step_type == "synthesis":
            return {"status": "success", "result_summary": {}, "skip_sql": True}
        if step.step_type == "report_generation":
            return {"status": "success", "result_summary": {"report_requested": True}, "skip_sql": True}

        question = STEP_QUESTIONS.get(step.output_key, step.goal)
        intent, plan, cannot = self.task_planner.plan(question, schema, memory)
        if cannot:
            return {"status": "failed", "error": cannot.get("reason", "Cannot answer"), "intent": intent}

        candidate = self.sql_generator.generate(question, schema, intent, memory.session, plan)
        if candidate.cannot_answer:
            return {"status": "failed", "error": candidate.error_message or candidate.reasoning, "intent": intent}

        return {
            "status": "pending_execution",
            "intent": intent,
            "analysis_plan": plan,
            "sql_candidate": candidate,
            "question": question,
        }

    def _quality_step(self, step, raw_df: pd.DataFrame | None, schema: TableSchema) -> dict[str, Any]:
        if raw_df is None:
            return {"status": "failed", "error": "No dataframe for quality check"}
        report = self.data_quality.analyze(raw_df, schema.to_dict())
        return {"status": "success", "result_summary": {"data_quality": report, **report}, "skip_sql": True, "extra": report}

    def _contribution_step(self, step, raw_df, schema, previous_outputs) -> dict[str, Any]:
        if raw_df is None:
            return {"status": "failed", "error": "No dataframe for contribution analysis"}
        result = self.contribution.analyze(raw_df, schema.to_dict())
        summary = {"contribution": result, "row_count": len(result.get("contributions", []))}
        return {"status": "success", "result_summary": summary, "skip_sql": True, "extra": result}
