from __future__ import annotations

from core.types import AnalysisPlan, IntentResult, TableSchema


class AnalysisPlanBuilder:
    CHART_MAP = {
        "trend": "line",
        "comparison": "bar",
        "ranking": "bar",
        "distribution": "histogram",
        "correlation": "scatter",
        "drill_down": "bar",
        "contribution_analysis": "bar",
        "data_quality": "bar",
    }

    def build(
        self,
        question: str,
        schema: TableSchema,
        intent: IntentResult,
        derived_from_memory: bool = False,
    ) -> AnalysisPlan:
        metrics = intent.metric_candidates
        dimensions = intent.dimension_candidates
        time_columns = intent.time_column_candidates
        agg = str(intent.options.get("aggregation", "sum")).upper()
        operations = self._build_operations(intent, metrics, dimensions, time_columns, agg)
        chart_type = intent.options.get("chart_type") or self.CHART_MAP.get(intent.task_type, "table")

        expected_output: dict = {"table": True, "explanation": True}
        if chart_type != "table":
            expected_output["chart"] = {
                "type": chart_type,
                "x": self._chart_x(intent, dimensions, time_columns),
                "y": f"{agg.lower()}_{metrics[0]}" if metrics else None,
                "color": dimensions[0] if intent.task_type == "trend" and dimensions else None,
            }

        return AnalysisPlan(
            task_type=intent.task_type,
            goal=self._goal(question, intent, metrics, dimensions),
            data_requirements={
                "metrics": metrics,
                "dimensions": dimensions,
                "time_columns": time_columns,
                "filters": intent.filters,
            },
            operations=operations,
            expected_output=expected_output,
            derived_from_memory=derived_from_memory,
            filters=intent.filters,
            notes=intent.notes,
        )

    def _goal(self, question: str, intent: IntentResult, metrics: list[str], dimensions: list[str]) -> str:
        metric = metrics[0] if metrics else "metric"
        dimension = dimensions[0] if dimensions else ""
        templates = {
            "trend": f"Analyze {metric} trend over time",
            "comparison": f"Compare {metric} by {dimension}" if dimension else f"Aggregate {metric}",
            "ranking": f"Rank {dimension} by {metric}" if dimension else f"Rank by {metric}",
            "data_quality": "Check data quality across columns",
            "contribution_analysis": f"Decompose change in {metric} by {dimension or 'dimension'}",
            "drill_down": f"Drill down {metric} by {dimension or 'sub-dimension'}",
            "distribution": f"Analyze distribution of {metric}",
            "correlation": "Analyze correlation between metrics",
            "lookup": "Preview data rows",
            "report_generation": "Generate analysis report from session history",
        }
        return templates.get(intent.task_type, question.strip())

    def _build_operations(
        self,
        intent: IntentResult,
        metrics: list[str],
        dimensions: list[str],
        time_columns: list[str],
        agg: str,
    ) -> list[dict]:
        ops: list[dict] = []
        if intent.task_type == "trend" and time_columns:
            ops.append({"type": "time_bucket", "column": time_columns[0], "granularity": "month"})
            group_cols = ["month"]
            if dimensions:
                group_cols.append(dimensions[0])
            ops.append({"type": "group_by", "columns": group_cols})
        elif intent.task_type in {"comparison", "ranking", "contribution_analysis", "drill_down"} and dimensions:
            ops.append({"type": "group_by", "columns": dimensions})
        if metrics and intent.task_type != "lookup":
            ops.append({"type": "aggregate", "function": agg, "column": metrics[0]})
        if intent.task_type == "ranking":
            ops.append({"type": "order_by", "direction": intent.options.get("sort_direction", "desc")})
        if intent.filters:
            ops.append({"type": "filter", "conditions": intent.filters})
        return ops

    def _chart_x(self, intent: IntentResult, dimensions: list[str], time_columns: list[str]) -> str | None:
        if intent.task_type == "trend":
            return "month"
        if dimensions:
            return dimensions[0]
        if time_columns:
            return time_columns[0]
        return None
