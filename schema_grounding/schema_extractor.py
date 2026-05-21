from __future__ import annotations

from typing import Any

import pandas as pd
from pandas.api.types import is_datetime64_any_dtype, is_numeric_dtype

from core.types import ColumnMeta, TableSchema
from schema_grounding.alias_manager import AliasManager
from schema_grounding.semantic_classifier import SemanticColumnClassifier
from data_layer.schema_extractor import SchemaExtractor as BaseSchemaExtractor


class EnhancedSchemaExtractor:
    def __init__(self) -> None:
        self.base = BaseSchemaExtractor()
        self.classifier = SemanticColumnClassifier()
        self.alias_manager = AliasManager()

    def extract(
        self,
        df: pd.DataFrame,
        table_name: str,
        dataset_id: str = "",
        column_mapping: dict[str, str] | None = None,
    ) -> TableSchema:
        base_schema = self.base.extract(df, table_name)
        row_count = base_schema.row_count
        enhanced_columns: list[ColumnMeta] = []
        for column in base_schema.columns:
            original_name = self._original_name(column.name, column_mapping)
            role = self.classifier.classify_role(column.name, column.dtype, column.semantic_type)
            quality_tags = self.classifier.quality_tags(
                column.name,
                column.dtype,
                column.missing_rate,
                column.unique_count,
                row_count,
                role,
            )
            semantic_type = column.semantic_type
            if role in {"metric", "dimension", "time", "id", "text", "boolean", "geo", "currency", "percentage"}:
                if role == "metric":
                    semantic_type = "metric"
                elif role == "time":
                    semantic_type = "time"
                elif role == "id":
                    semantic_type = "id"
                elif role == "dimension":
                    semantic_type = "category"
            enhanced_columns.append(
                ColumnMeta(
                    name=column.name,
                    dtype=column.dtype,
                    semantic_type=semantic_type,
                    sample_values=column.sample_values,
                    missing_rate=column.missing_rate,
                    unique_count=column.unique_count,
                    min_value=column.min_value,
                    max_value=column.max_value,
                    mean_value=column.mean_value,
                    role=role,
                    quality_tags=quality_tags,
                    original_name=original_name,
                    aliases=self.alias_manager.build_aliases(column.name, original_name),
                )
            )

        likely_metrics = [c.name for c in enhanced_columns if c.role == "metric" or c.semantic_type == "metric"]
        likely_dimensions = [c.name for c in enhanced_columns if c.role == "dimension" or c.semantic_type == "category"]
        likely_time_columns = [c.name for c in enhanced_columns if c.role == "time" or c.semantic_type == "time"]
        time_range = self._table_time_range(df, likely_time_columns)

        return TableSchema(
            table_name=table_name,
            row_count=row_count,
            columns=enhanced_columns,
            dataset_id=dataset_id or table_name,
            time_range=time_range,
            likely_metrics=likely_metrics,
            likely_dimensions=likely_dimensions,
            likely_time_columns=likely_time_columns,
        )

    def _original_name(self, normalized: str, mapping: dict[str, str] | None) -> str:
        if not mapping:
            return normalized
        for original, name in mapping.items():
            if name == normalized:
                return original
        return normalized

    def _table_time_range(self, df: pd.DataFrame, time_columns: list[str]) -> dict[str, Any] | None:
        for column in time_columns:
            if column not in df.columns:
                continue
            series = df[column]
            if not is_datetime64_any_dtype(series):
                series = pd.to_datetime(series, errors="coerce")
            clean = series.dropna()
            if clean.empty:
                continue
            return {
                "column": column,
                "min": clean.min().isoformat() if hasattr(clean.min(), "isoformat") else str(clean.min()),
                "max": clean.max().isoformat() if hasattr(clean.max(), "isoformat") else str(clean.max()),
            }
        return None
