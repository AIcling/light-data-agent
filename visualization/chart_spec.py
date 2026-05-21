from __future__ import annotations

from typing import Any

from core.types import AnalysisPlan, IntentResult


CHART_TYPE_ALIASES = {
    "line_chart": "line",
    "bar_chart": "bar",
    "scatter_plot": "scatter",
    "histogram": "histogram",
    "table": "table",
}


def normalize_chart_type(chart_type: str) -> str:
    return CHART_TYPE_ALIASES.get(chart_type, chart_type)


def build_chart_spec(
    task_type: str,
    result_columns: list[str],
    numeric_columns: list[str],
    non_numeric_columns: list[str],
    plan: AnalysisPlan | None = None,
    intent: IntentResult | None = None,
) -> dict[str, Any] | None:
    if plan and plan.expected_output.get("chart"):
        spec = dict(plan.expected_output["chart"])
        spec["chart_type"] = normalize_chart_type(spec.get("type", "table"))
        spec["reason"] = f"Recommended for {task_type} task."
        return _validate_spec_fields(spec, result_columns)

    chart_type = {
        "trend": "line",
        "comparison": "bar",
        "ranking": "bar",
        "distribution": "histogram",
        "correlation": "scatter",
        "drill_down": "bar",
        "contribution_analysis": "bar",
        "data_quality": "bar",
    }.get(task_type, "table")

    if chart_type == "table":
        return {"chart_type": "table", "title": "Query Result", "reason": "Default table view."}

    if chart_type == "line":
        x = _first(result_columns, ["month", "date", "order_date"]) or (non_numeric_columns[0] if non_numeric_columns else None)
        y = numeric_columns[0] if numeric_columns else None
        color = next((c for c in non_numeric_columns if c != x), None)
    elif chart_type == "bar":
        x = non_numeric_columns[0] if non_numeric_columns else result_columns[0]
        y = numeric_columns[0] if numeric_columns else None
        color = None
    elif chart_type == "histogram":
        x = numeric_columns[0] if numeric_columns else result_columns[0]
        y = None
        color = None
    elif chart_type == "scatter":
        if len(numeric_columns) < 2:
            return None
        x, y = numeric_columns[0], numeric_columns[1]
        color = non_numeric_columns[0] if non_numeric_columns else None
    else:
        return None

    if x is None or (chart_type != "histogram" and y is None):
        return None

    spec: dict[str, Any] = {
        "chart_type": chart_type,
        "x": x,
        "title": _title(task_type),
        "reason": f"The task is a {task_type} analysis.",
        "limit": 100,
    }
    if y:
        spec["y"] = y
    if color:
        spec["color"] = color
    return _validate_spec_fields(spec, result_columns)


def _validate_spec_fields(spec: dict[str, Any], columns: list[str]) -> dict[str, Any] | None:
    col_set = set(columns)
    for field in ("x", "y", "color"):
        value = spec.get(field)
        if value and value not in col_set:
            return None
    return spec


def _first(columns: list[str], candidates: list[str]) -> str | None:
    lower_map = {c.lower(): c for c in columns}
    for candidate in candidates:
        if candidate in lower_map:
            return lower_map[candidate]
    return None


def _title(task_type: str) -> str:
    return {
        "trend": "Trend Analysis",
        "comparison": "Comparison",
        "ranking": "Ranking",
        "distribution": "Distribution",
        "correlation": "Correlation",
        "data_quality": "Data Quality",
        "contribution_analysis": "Contribution Analysis",
    }.get(task_type, "Query Result")
