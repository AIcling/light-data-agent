from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from core.types import TableSchema


@dataclass
class DatasetMemory:
    dataset_id: str
    source_type: str = "csv"
    tables: list[str] = field(default_factory=list)
    schema_summary: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    last_used_at: str = ""
    common_metrics: list[str] = field(default_factory=list)
    common_dimensions: list[str] = field(default_factory=list)
    common_time_columns: list[str] = field(default_factory=list)
    known_aliases: dict[str, str] = field(default_factory=dict)
    metric_usage: dict[str, int] = field(default_factory=dict)
    dimension_usage: dict[str, int] = field(default_factory=dict)

    @classmethod
    def from_schema(cls, schema: TableSchema, source_type: str = "csv") -> "DatasetMemory":
        now = datetime.now(timezone.utc).isoformat()
        return cls(
            dataset_id=schema.dataset_id or schema.table_name,
            source_type=source_type,
            tables=[schema.table_name],
            schema_summary=schema.to_dict(),
            created_at=now,
            last_used_at=now,
            common_metrics=list(schema.likely_metrics),
            common_dimensions=list(schema.likely_dimensions),
            common_time_columns=list(schema.likely_time_columns),
        )

    def touch(self) -> None:
        self.last_used_at = datetime.now(timezone.utc).isoformat()

    def record_usage(self, metrics: list[str], dimensions: list[str]) -> None:
        for metric in metrics:
            self.metric_usage[metric] = self.metric_usage.get(metric, 0) + 1
        for dimension in dimensions:
            self.dimension_usage[dimension] = self.dimension_usage.get(dimension, 0) + 1
        self.touch()

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "source_type": self.source_type,
            "tables": self.tables,
            "schema_summary": self.schema_summary,
            "created_at": self.created_at,
            "last_used_at": self.last_used_at,
            "common_metrics": self.common_metrics,
            "common_dimensions": self.common_dimensions,
            "common_time_columns": self.common_time_columns,
            "known_aliases": self.known_aliases,
            "metric_usage": self.metric_usage,
            "dimension_usage": self.dimension_usage,
        }
