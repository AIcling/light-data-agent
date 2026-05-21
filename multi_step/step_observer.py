from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from multi_step.multi_step_plan import PlanStep


@dataclass
class StepObserver:
    min_trend_points: int = 3

    def observe(
        self,
        step: PlanStep,
        result_summary: dict[str, Any],
        result_df: pd.DataFrame | None = None,
        extra: dict[str, Any] | None = None,
    ) -> list[str]:
        observations: list[str] = []
        if result_summary.get("empty_result"):
            observations.append(f"Step '{step.goal}' returned no rows.")
            return observations

        row_count = result_summary.get("row_count", 0)
        observations.append(f"Step '{step.goal}' returned {row_count} rows.")

        trend = result_summary.get("trend")
        if trend == "decreasing":
            observations.append("Result shows a decreasing trend.")
        elif trend == "increasing":
            observations.append("Result shows an increasing trend.")

        numeric = result_summary.get("numeric_summary", {})
        for col, stats in list(numeric.items())[:1]:
            if stats.get("max") is not None and stats.get("min") is not None:
                observations.append(f"{col} ranges from {stats.get('min')} to {stats.get('max')}.")

        if extra and extra.get("observation"):
            observations.append(str(extra["observation"]))

        if extra and extra.get("contributions"):
            for item in extra["contributions"][:2]:
                observations.append(
                    f"{item.get('dimension')} contributed about {item.get('contribution_pct')}% of the change."
                )

        if extra and extra.get("quality_score") is not None:
            observations.append(f"Data quality score: {extra['quality_score']}/100.")

        step.observations = observations
        return observations
