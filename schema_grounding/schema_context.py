from __future__ import annotations

from typing import Any

from core.types import TableSchema


class SchemaContextBuilder:
    def build(self, schema: TableSchema, relevant_fields: dict[str, Any] | None = None) -> dict[str, Any]:
        relevant_column_names = []
        if relevant_fields:
            relevant_column_names = [c["name"] for c in relevant_fields.get("relevant_columns", [])]

        columns_context = []
        for column in schema.columns:
            if relevant_column_names and column.name not in relevant_column_names:
                continue
            columns_context.append(
                {
                    "name": column.name,
                    "dtype": column.dtype,
                    "semantic_type": column.semantic_type,
                    "role": column.role,
                    "missing_rate": column.missing_rate,
                    "quality_tags": column.quality_tags,
                    "aliases": column.aliases,
                }
            )

        return {
            "dataset_id": schema.dataset_id or schema.table_name,
            "table_name": schema.table_name,
            "row_count": schema.row_count,
            "column_count": len(schema.columns),
            "time_range": schema.time_range,
            "likely_metrics": schema.likely_metrics,
            "likely_dimensions": schema.likely_dimensions,
            "likely_time_columns": schema.likely_time_columns,
            "columns": columns_context if columns_context else [c.to_dict() for c in schema.columns],
            "relevant_fields": relevant_fields,
        }
