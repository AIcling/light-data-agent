from __future__ import annotations

from typing import Any

from core.types import TableSchema
from memory.memory_store import MemoryStore
from schema_grounding.alias_manager import AliasManager


class RelevantFieldSelector:
    def __init__(self, alias_manager: AliasManager | None = None) -> None:
        self.alias_manager = alias_manager or AliasManager()

    def select(
        self,
        question: str,
        schema: TableSchema,
        memory: MemoryStore | None = None,
    ) -> dict[str, Any]:
        lowered = question.lower()
        relevant_columns: list[dict[str, str]] = []
        missing_concepts: list[str] = []

        for column in schema.columns:
            reason = self._match_reason(column, lowered, memory)
            if reason:
                relevant_columns.append({"name": column.name, "reason": reason})

        if memory and memory.session.last_metric:
            if not any(c["name"] == memory.session.last_metric for c in relevant_columns):
                relevant_columns.append(
                    {"name": memory.session.last_metric, "reason": "Recently used metric from memory."}
                )
        if memory and memory.session.last_dimension:
            dim = memory.session.last_dimension
            if dim and not any(c["name"] == dim for c in relevant_columns):
                relevant_columns.append({"name": dim, "reason": "Recently used dimension from memory."})

        if not relevant_columns:
            for name in schema.likely_metrics[:2] + schema.likely_dimensions[:2] + schema.likely_time_columns[:1]:
                if name and not any(c["name"] == name for c in relevant_columns):
                    relevant_columns.append({"name": name, "reason": "Default schema field."})

        return {
            "relevant_tables": [schema.table_name],
            "relevant_columns": relevant_columns,
            "missing_concepts": missing_concepts,
        }

    def _match_reason(self, column, lowered: str, memory: MemoryStore | None) -> str | None:
        name_lower = column.name.lower()
        if name_lower in lowered:
            return f"Question mentions column {column.name}."
        for alias in column.aliases:
            if alias.lower() in lowered:
                return f"Question matches alias '{alias}' for {column.name}."
        if memory:
            if column.name == memory.session.last_metric:
                return "Recently used metric."
            if column.name == memory.session.last_dimension:
                return "Recently used dimension."
            if column.name == memory.session.last_time_column:
                return "Recently used time column."
        task_hints = {
            "time": ["趋势", "每月", "按月", "月份", "trend", "monthly", "month", "over time"],
            "metric": ["销售", "利润", "sales", "profit", "amount", "sum", "平均", "avg"],
            "dimension": ["地区", "类别", "region", "category", "不同", "各", "by "],
        }
        if column.role == "time" or column.semantic_type == "time":
            if any(h in lowered for h in task_hints["time"]):
                return "Time-related question."
        if column.role == "metric" or column.semantic_type == "metric":
            if any(h in lowered for h in task_hints["metric"]):
                return "Metric-related question."
        if column.role == "dimension" or column.semantic_type == "category":
            if any(h in lowered for h in task_hints["dimension"]):
                return "Dimension-related question."
        return None
