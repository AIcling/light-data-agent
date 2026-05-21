from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.types import IntentResult


@dataclass
class SessionMemory:
    session_id: str = ""
    active_dataset_id: str = ""
    last_question: str = ""
    last_resolved_query: str = ""
    last_sql: str = ""
    last_task_type: str = ""
    last_metric: str = ""
    last_dimension: str = ""
    last_dimensions: list[str] = field(default_factory=list)
    last_time_column: str = ""
    last_result_summary: dict[str, Any] = field(default_factory=dict)
    last_chart_spec: dict[str, Any] = field(default_factory=dict)
    last_analysis_id: str = ""
    project_id: str = ""
    history: list[dict[str, Any]] = field(default_factory=list)
    user_preferences: dict[str, Any] = field(default_factory=lambda: {
        "preferred_language": "zh",
        "preferred_chart_style": "plotly",
        "show_sql_by_default": True,
        "show_debug_trace": False,
        "default_limit": 100,
    })

    def update(
        self,
        question: str,
        intent: IntentResult,
        sql: str,
        result_summary: dict[str, Any],
        resolved_query: str = "",
        chart_spec: dict[str, Any] | None = None,
    ) -> None:
        self.last_question = question
        self.last_resolved_query = resolved_query or question
        self.last_sql = sql
        self.last_task_type = intent.task_type
        self.last_metric = intent.metric_candidates[0] if intent.metric_candidates else ""
        self.last_dimension = (
            intent.dimension_candidates[0] if intent.dimension_candidates else ""
        )
        self.last_dimensions = list(intent.dimension_candidates)
        self.last_time_column = (
            intent.time_column_candidates[0] if intent.time_column_candidates else ""
        )
        self.last_result_summary = result_summary
        if chart_spec:
            self.last_chart_spec = chart_spec
        self.history.append(self.to_dict(include_history=False))
        self.history = self.history[-10:]

    def to_dict(self, include_history: bool = True) -> dict[str, Any]:
        data = {
            "session_id": self.session_id,
            "active_dataset_id": self.active_dataset_id,
            "last_question": self.last_question,
            "last_resolved_query": self.last_resolved_query,
            "last_sql": self.last_sql,
            "last_task_type": self.last_task_type,
            "last_metric": self.last_metric,
            "last_dimension": self.last_dimension,
            "last_dimensions": self.last_dimensions,
            "last_time_column": self.last_time_column,
            "last_result_summary": self.last_result_summary,
            "last_chart_spec": self.last_chart_spec,
            "last_analysis_id": self.last_analysis_id,
            "project_id": self.project_id,
            "user_preferences": self.user_preferences,
        }
        if include_history:
            data["history"] = self.history
        return data

    def clear(self) -> None:
        self.last_question = ""
        self.last_resolved_query = ""
        self.last_sql = ""
        self.last_task_type = ""
        self.last_metric = ""
        self.last_dimension = ""
        self.last_dimensions = []
        self.last_time_column = ""
        self.last_result_summary = {}
        self.last_chart_spec = {}
        self.history = []
