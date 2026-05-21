from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from multi_step.multi_step_plan import PlanStep


@dataclass
class ResultCritic:
    min_trend_points: int = 3

    def critique(
        self,
        step: PlanStep,
        result_summary: dict[str, Any],
        result_df: pd.DataFrame | None = None,
    ) -> list[str]:
        warnings: list[str] = []
        if result_summary.get("empty_result"):
            warnings.append("Empty result may block downstream steps.")
        row_count = result_summary.get("row_count", 0)
        if row_count == 1 and step.step_type == "sql_query":
            warnings.append("Only one row returned; dimension breakdown may be incomplete.")
        if row_count > 0 and row_count < self.min_trend_points and "trend" in step.goal.lower():
            warnings.append(f"Fewer than {self.min_trend_points} data points for trend analysis.")
        numeric = result_summary.get("numeric_summary", {})
        for col, stats in numeric.items():
            if stats.get("max") == stats.get("min") and stats.get("max") is not None:
                warnings.append(f"{col} has zero variance in results.")
        step.warnings = warnings
        return warnings
