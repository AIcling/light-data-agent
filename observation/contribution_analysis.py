from __future__ import annotations

from typing import Any

import pandas as pd


class ContributionAnalyzer:
    """Primary contribution decomposition — not causal inference."""

    def analyze(
        self,
        df: pd.DataFrame,
        schema_summary: dict[str, Any],
        metric: str | None = None,
        dimension: str | None = None,
        time_column: str | None = None,
    ) -> dict[str, Any]:
        likely_metrics = schema_summary.get("likely_metrics", [])
        likely_dimensions = schema_summary.get("likely_dimensions", [])
        likely_time = schema_summary.get("likely_time_columns", [])

        metric = metric or (likely_metrics[0] if likely_metrics else None)
        dimension = dimension or (likely_dimensions[0] if likely_dimensions else None)
        time_column = time_column or (likely_time[0] if likely_time else None)

        if not metric or metric not in df.columns:
            return {"supported": False, "reason": "No suitable metric column found."}
        if not time_column or time_column not in df.columns:
            return {"supported": False, "reason": "Contribution analysis requires a time column."}
        if not dimension or dimension not in df.columns:
            return {"supported": False, "reason": "Contribution analysis requires a dimension column."}

        work = df.copy()
        work[time_column] = pd.to_datetime(work[time_column], errors="coerce")
        work = work.dropna(subset=[time_column, metric])
        if work.empty:
            return {"supported": False, "reason": "No valid rows for contribution analysis."}

        work["period"] = work[time_column].dt.to_period("M").astype(str)
        periods = sorted(work["period"].unique())
        if len(periods) < 2:
            return {"supported": False, "reason": "Need at least two time periods."}

        current_period, previous_period = periods[-1], periods[-2]
        current = work[work["period"] == current_period].groupby(dimension)[metric].sum()
        previous = work[work["period"] == previous_period].groupby(dimension)[metric].sum()
        all_dims = current.index.union(previous.index)
        changes = []
        total_change = float(current.sum() - previous.sum())
        for dim_value in all_dims:
            curr = float(current.get(dim_value, 0))
            prev = float(previous.get(dim_value, 0))
            delta = curr - prev
            contribution_pct = (delta / total_change * 100) if total_change else 0
            changes.append({
                "dimension": str(dim_value),
                "current": curr,
                "previous": prev,
                "change": delta,
                "contribution_pct": round(contribution_pct, 1),
            })
        changes.sort(key=lambda x: abs(x["change"]), reverse=True)

        pct_change = (total_change / previous.sum() * 100) if previous.sum() else 0
        direction = "下降" if total_change < 0 else "上升"

        return {
            "supported": True,
            "observation": (
                f"{current_period} 的 {metric} 相比 {previous_period} {direction} "
                f"{abs(pct_change):.1f}%。"
            ),
            "total_change": total_change,
            "current_period": current_period,
            "previous_period": previous_period,
            "contributions": changes[:10],
            "limitations": [
                "这是贡献分解，不是因果分析。",
                "当前数据可能缺少促销、价格、库存或渠道字段，无法确认根本原因。",
            ],
            "next_steps": [
                f"可以继续分析 {changes[0]['dimension']} 在不同产品类别的 {metric} 变化。"
                if changes else "可以继续按其他维度拆分。",
            ],
        }
