from __future__ import annotations

from typing import Any

import pandas as pd


class InsightGenerator:
    def generate(
        self,
        result_summary: dict[str, Any],
        task_type: str,
        contribution: dict[str, Any] | None = None,
        quality: dict[str, Any] | None = None,
    ) -> tuple[list[str], list[str]]:
        insights: list[str] = []
        limitations: list[str] = []

        if result_summary.get("empty_result"):
            limitations.append("查询未返回数据，结论有限。")
            return insights, limitations

        trend = result_summary.get("trend")
        if trend == "increasing":
            insights.append("查询结果整体呈上升趋势。")
        elif trend == "decreasing":
            insights.append("查询结果整体呈下降趋势。")

        numeric = result_summary.get("numeric_summary", {})
        for column, stats in list(numeric.items())[:2]:
            if stats.get("max") is not None and stats.get("min") is not None:
                insights.append(
                    f"{column} 的范围为 {stats.get('min')} 到 {stats.get('max')}。"
                )

        category_top = result_summary.get("category_top_values", {})
        for column, values in list(category_top.items())[:1]:
            if values:
                top_item = next(iter(values.items()))
                insights.append(f"{column} 的最高频值为 {top_item[0]}。")

        if contribution and contribution.get("supported"):
            insights.append(contribution.get("observation", ""))
            top = contribution.get("contributions", [])[:2]
            if top:
                parts = [
                    f"{item['dimension']} 贡献了约 {abs(item['contribution_pct'])}% 的变化"
                    for item in top
                ]
                insights.append("贡献分解：" + "，".join(parts) + "。")
            limitations.extend(contribution.get("limitations", []))

        if quality:
            score = quality.get("quality_score")
            if score is not None:
                insights.append(f"数据质量评分为 {score}/100。")
            limitations.extend(quality.get("recommendations", [])[:2])

        limitations.append("以上结论基于当前查询结果，不能直接证明因果关系。")
        return [i for i in insights if i], list(dict.fromkeys(limitations))
