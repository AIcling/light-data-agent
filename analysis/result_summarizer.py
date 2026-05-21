from __future__ import annotations

from typing import Any

import pandas as pd
from pandas.api.types import is_datetime64_any_dtype, is_numeric_dtype


class ResultSummarizer:
    def summarize(self, df: pd.DataFrame) -> dict[str, Any]:
        summary: dict[str, Any] = {
            "row_count": int(len(df)),
            "columns": [str(c) for c in df.columns],
            "empty_result": df.empty,
            "numeric_summary": {},
            "category_top_values": {},
            "time_range": {},
            "trend": None,
            "alerts": [],
        }
        if df.empty:
            summary["alerts"].append("Query returned no rows.")
            return summary

        for column in df.columns:
            series = df[column]
            if is_numeric_dtype(series):
                summary["numeric_summary"][str(column)] = self._numeric_summary(series)
            elif is_datetime64_any_dtype(series):
                summary["time_range"][str(column)] = self._time_range(series)
            else:
                parsed = pd.to_datetime(series, errors="coerce")
                if parsed.notna().mean() >= 0.8:
                    summary["time_range"][str(column)] = self._time_range(parsed)
                else:
                    summary["category_top_values"][str(column)] = (
                        series.astype(str).value_counts(dropna=True).head(5).to_dict()
                    )

        summary["trend"] = self._detect_simple_trend(df)
        return summary

    def _numeric_summary(self, series: pd.Series) -> dict[str, Any]:
        clean = series.dropna()
        if clean.empty:
            return {"min": None, "max": None, "mean": None, "sum": None}
        return {
            "min": self._safe(clean.min()),
            "max": self._safe(clean.max()),
            "mean": float(clean.mean()),
            "sum": self._safe(clean.sum()),
        }

    def _time_range(self, series: pd.Series) -> dict[str, Any]:
        clean = pd.to_datetime(series.dropna(), errors="coerce").dropna()
        if clean.empty:
            return {"min": None, "max": None}
        return {
            "min": clean.min().isoformat(),
            "max": clean.max().isoformat(),
        }

    def _detect_simple_trend(self, df: pd.DataFrame) -> str | None:
        numeric_columns = [column for column in df.columns if is_numeric_dtype(df[column])]
        if not numeric_columns or len(df) < 2:
            return None
        series = df[numeric_columns[0]].dropna()
        if len(series) < 2:
            return None
        first = float(series.iloc[0])
        last = float(series.iloc[-1])
        if abs(last - first) < 1e-9:
            return "flat"
        return "increasing" if last > first else "decreasing"

    def _safe(self, value: Any) -> Any:
        if pd.isna(value):
            return None
        if hasattr(value, "item"):
            try:
                return value.item()
            except Exception:
                pass
        return value
