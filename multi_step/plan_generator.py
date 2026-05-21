from __future__ import annotations

import uuid
from dataclasses import dataclass

from core.types import TableSchema
from memory.memory_store import MemoryStore
from multi_step.multi_step_plan import MultiStepAnalysisPlan, PlanStep


@dataclass
class PlanGenerator:
    max_steps: int = 6

    def generate(
        self,
        decomposition: dict,
        question: str,
        schema: TableSchema,
        project_id: str,
        dataset_id: str,
    ) -> MultiStepAnalysisPlan:
        plan_type = decomposition.get("plan_type", "custom")
        subgoals = decomposition.get("subgoals", [])[: self.max_steps]
        steps: list[PlanStep] = []
        prev_ids: list[str] = []

        if plan_type == "contribution_analysis":
            steps = self._contribution_steps(schema, subgoals)
        elif plan_type == "data_quality":
            steps = self._quality_steps(subgoals)
        elif plan_type == "report_generation":
            steps = self._report_steps(schema, subgoals)
        elif plan_type == "overview":
            steps = self._overview_steps(schema, subgoals)
        else:
            for idx, subgoal in enumerate(subgoals):
                step_id = f"step_{idx + 1:03d}"
                steps.append(
                    PlanStep(
                        step_id=step_id,
                        step_type="sql_query" if idx < len(subgoals) - 1 else "synthesis",
                        goal=subgoal,
                        depends_on=list(prev_ids),
                        input_refs=[s.output_key for s in steps if s.output_key],
                        output_key=f"step_{idx + 1}_output",
                    )
                )
                prev_ids.append(step_id)

        if steps and steps[-1].step_type != "synthesis":
            synth_id = f"step_{len(steps) + 1:03d}"
            steps.append(
                PlanStep(
                    step_id=synth_id,
                    step_type="synthesis",
                    goal="Summarize all step results, limitations, and next steps",
                    depends_on=[s.step_id for s in steps],
                    input_refs=[s.output_key for s in steps if s.output_key],
                    output_key="final_explanation",
                )
            )

        return MultiStepAnalysisPlan(
            plan_id=f"plan_{uuid.uuid4().hex[:10]}",
            project_id=project_id,
            dataset_id=dataset_id,
            goal=question,
            plan_type=plan_type,
            steps=steps[: self.max_steps],
            final_outputs={"summary": True, "charts": True, "report": plan_type == "report_generation"},
        )

    def _contribution_steps(self, schema: TableSchema, subgoals: list[str]) -> list[PlanStep]:
        metric = schema.likely_metrics[0] if schema.likely_metrics else "sales_amount"
        time_col = schema.likely_time_columns[0] if schema.likely_time_columns else "order_date"
        region = next((d for d in schema.likely_dimensions if "region" in d.lower()), schema.likely_dimensions[0] if schema.likely_dimensions else "region")
        category = next((d for d in schema.likely_dimensions if "product" in d.lower() or "category" in d.lower()), schema.likely_dimensions[-1] if schema.likely_dimensions else "product_category")
        return [
            PlanStep("step_001", "sql_query", subgoals[0] if subgoals else "Compare periods", [], [], "monthly_compare"),
            PlanStep("step_002", "sql_query", subgoals[1] if len(subgoals) > 1 else "By region", ["step_001"], ["monthly_compare"], "region_contribution"),
            PlanStep("step_003", "sql_query", subgoals[2] if len(subgoals) > 2 else "By category", ["step_001"], ["monthly_compare"], "category_contribution"),
            PlanStep("step_004", "contribution_decomposition", "Run contribution analysis", ["step_001", "step_002"], ["monthly_compare", "region_contribution"], "contribution_result"),
            PlanStep("step_005", "synthesis", subgoals[-1] if subgoals else "Synthesize", ["step_001", "step_002", "step_003", "step_004"], ["monthly_compare", "region_contribution", "category_contribution", "contribution_result"], "final_explanation"),
        ]

    def _quality_steps(self, subgoals: list[str]) -> list[PlanStep]:
        return [
            PlanStep("step_001", "data_quality_check", subgoals[0] if subgoals else "Missing values", [], [], "missing_check"),
            PlanStep("step_002", "data_quality_check", subgoals[1] if len(subgoals) > 1 else "Duplicates", [], [], "duplicate_check"),
            PlanStep("step_003", "synthesis", subgoals[-1] if subgoals else "Quality summary", ["step_001", "step_002"], ["missing_check", "duplicate_check"], "final_explanation"),
        ]

    def _report_steps(self, schema: TableSchema, subgoals: list[str]) -> list[PlanStep]:
        metric = schema.likely_metrics[0] if schema.likely_metrics else "sales_amount"
        dim = schema.likely_dimensions[0] if schema.likely_dimensions else "region"
        return [
            PlanStep("step_001", "data_quality_check", "Dataset quality scan", [], [], "quality_scan"),
            PlanStep("step_002", "sql_query", f"Summarize {metric}", ["step_001"], ["quality_scan"], "metric_summary"),
            PlanStep("step_003", "sql_query", f"Compare {metric} by {dim}", ["step_002"], ["metric_summary"], "dimension_compare"),
            PlanStep("step_004", "sql_query", f"Trend of {metric} over time", ["step_002"], ["metric_summary"], "trend_summary"),
            PlanStep("step_005", "report_generation", "Generate report", ["step_001", "step_002", "step_003", "step_004"], ["quality_scan", "metric_summary", "dimension_compare", "trend_summary"], "final_report"),
            PlanStep("step_006", "synthesis", "Executive summary", ["step_005"], ["final_report"], "final_explanation"),
        ]

    def _overview_steps(self, schema: TableSchema, subgoals: list[str]) -> list[PlanStep]:
        metric = schema.likely_metrics[0] if schema.likely_metrics else "sales_amount"
        dim = schema.likely_dimensions[0] if schema.likely_dimensions else "region"
        return [
            PlanStep("step_001", "sql_query", "Dataset preview", [], [], "preview"),
            PlanStep("step_002", "sql_query", f"Aggregate {metric}", ["step_001"], ["preview"], "metric_summary"),
            PlanStep("step_003", "sql_query", f"Top {dim} by {metric}", ["step_002"], ["metric_summary"], "top_dimension"),
            PlanStep("step_004", "synthesis", "Overview synthesis", ["step_001", "step_002", "step_003"], ["preview", "metric_summary", "top_dimension"], "final_explanation"),
        ]
