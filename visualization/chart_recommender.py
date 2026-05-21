from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd
from pandas.api.types import is_numeric_dtype

from core.types import AnalysisPlan, IntentResult
from visualization.chart_spec import build_chart_spec


@dataclass
class ChartRecommender:
    def recommend(
        self,
        intent: IntentResult,
        result_df: pd.DataFrame,
        result_summary: dict[str, Any],
        plan: AnalysisPlan | None = None,
    ) -> dict[str, Any] | None:
        if result_df.empty:
            return None
        numeric_columns = [str(c) for c in result_df.columns if is_numeric_dtype(result_df[c])]
        non_numeric_columns = [str(c) for c in result_df.columns if c not in numeric_columns]
        chart_override = intent.options.get("chart_type")
        spec = build_chart_spec(
            intent.task_type,
            [str(c) for c in result_df.columns],
            numeric_columns,
            non_numeric_columns,
            plan,
            intent,
        )
        if spec and chart_override:
            spec["chart_type"] = chart_override
        return spec
