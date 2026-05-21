from __future__ import annotations

from typing import Any

import pandas as pd
from pandas.api.types import (
    is_bool_dtype,
    is_datetime64_any_dtype,
    is_float_dtype,
    is_integer_dtype,
    is_numeric_dtype,
)

from core.types import ColumnMeta, TableSchema


class SchemaExtractor:
    def extract(self, df: pd.DataFrame, table_name: str) -> TableSchema:
        columns = [self._extract_column(df, column) for column in df.columns]
        return TableSchema(
            table_name=table_name,
            row_count=int(len(df)),
            columns=columns,
        )

    def _extract_column(self, df: pd.DataFrame, column_name: str) -> ColumnMeta:
        series = df[column_name]
        dtype = self._dtype_name(series)
        missing_rate = float(series.isna().mean()) if len(series) else 0.0
        unique_count = int(series.nunique(dropna=True))
        sample_values = self._sample_values(series)
        min_value: Any | None = None
        max_value: Any | None = None
        mean_value: float | None = None

        if is_numeric_dtype(series):
            min_value = self._safe_value(series.min(skipna=True))
            max_value = self._safe_value(series.max(skipna=True))
            mean = series.mean(skipna=True)
            mean_value = None if pd.isna(mean) else float(mean)
        elif is_datetime64_any_dtype(series):
            min_value = self._safe_value(series.min(skipna=True))
            max_value = self._safe_value(series.max(skipna=True))

        semantic_type = self._semantic_type(column_name, series, dtype, unique_count)
        return ColumnMeta(
            name=column_name,
            dtype=dtype,
            semantic_type=semantic_type,
            sample_values=sample_values,
            missing_rate=missing_rate,
            unique_count=unique_count,
            min_value=min_value,
            max_value=max_value,
            mean_value=mean_value,
        )

    def _dtype_name(self, series: pd.Series) -> str:
        if is_datetime64_any_dtype(series):
            return "date"
        if is_bool_dtype(series):
            return "bool"
        if is_integer_dtype(series):
            return "int"
        if is_float_dtype(series):
            return "float"
        return "string"

    def _semantic_type(
        self,
        column_name: str,
        series: pd.Series,
        dtype: str,
        unique_count: int,
    ) -> str:
        lowered = column_name.lower()
        row_count = max(len(series), 1)
        unique_ratio = unique_count / row_count
        if any(token in lowered for token in ("date", "time", "day", "month", "year")):
            return "time"
        if dtype == "date":
            return "time"
        if "id" in lowered or unique_ratio > 0.95:
            return "id"
        if dtype in {"int", "float"} and unique_count > min(10, row_count * 0.2):
            return "metric"
        if dtype in {"int", "float"}:
            return "metric"
        average_length = self._average_string_length(series)
        if average_length >= 60:
            return "text"
        if unique_count <= max(20, int(row_count * 0.5)):
            return "category"
        return "unknown"

    def _sample_values(self, series: pd.Series) -> list[Any]:
        values = series.dropna().drop_duplicates().head(5).tolist()
        return [self._safe_value(value) for value in values]

    def _safe_value(self, value: Any) -> Any:
        if pd.isna(value):
            return None
        if isinstance(value, pd.Timestamp):
            return value.isoformat()
        if hasattr(value, "item"):
            try:
                return value.item()
            except Exception:
                pass
        return value

    def _average_string_length(self, series: pd.Series) -> float:
        non_null = series.dropna()
        if non_null.empty:
            return 0.0
        return float(non_null.astype(str).str.len().mean())
