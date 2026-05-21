from __future__ import annotations

from typing import Any

from core.types import AnalysisPlan, IntentResult


class ResultExplainer:
    def explain(
        self,
        question: str,
        sql: str,
        result_summary: dict[str, Any],
        intent: IntentResult | None = None,
        plan: AnalysisPlan | None = None,
        insights: list[str] | None = None,
        limitations: list[str] | None = None,
        contribution: dict[str, Any] | None = None,
    ) -> str:
        structured = self.explain_structured(
            question, sql, result_summary, intent, plan, insights, limitations, contribution
        )
        sections = [
            f"查询目的：\n{structured['purpose']}",
            f"主要观察结果：\n{structured['observations']}",
            f"数据证据：\n{structured['evidence']}",
            f"可能解释：\n{structured['possible_explanations']}",
            f"限制：\n{structured['limitations']}",
            f"下一步建议：\n{structured['next_steps']}",
        ]
        return "\n\n".join(sections)

    def explain_structured(
        self,
        question: str,
        sql: str,
        result_summary: dict[str, Any],
        intent: IntentResult | None = None,
        plan: AnalysisPlan | None = None,
        insights: list[str] | None = None,
        limitations: list[str] | None = None,
        contribution: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        task_type = intent.task_type if intent else "analysis"
        purpose = plan.goal if plan else question

        if result_summary.get("empty_result"):
            return {
                "purpose": purpose,
                "observations": "查询没有返回数据。",
                "evidence": "结果表为空。",
                "possible_explanations": "可能是筛选条件过严，或相关字段值为空。",
                "limitations": "无法基于空结果得出业务结论。",
                "next_steps": "建议放宽筛选条件，或先查看数据预览和 Schema。",
            }

        row_count = result_summary.get("row_count", 0)
        observations = insights[0] if insights else f"本次查询返回 {row_count} 行结果。"
        if len(insights or []) > 1:
            observations += " " + " ".join(insights[1:3])

        evidence_parts = [f"结果表包含 {row_count} 行记录。"]
        numeric_summary = result_summary.get("numeric_summary", {})
        for column, stats in list(numeric_summary.items())[:2]:
            evidence_parts.append(
                f"{column} 的最小值为 {stats.get('min')}，最大值为 {stats.get('max')}，"
                f"平均值约为 {self._round(stats.get('mean'))}。"
            )
        if contribution and contribution.get("supported"):
            evidence_parts.append(contribution.get("observation", ""))

        possible = (
            "从当前数据只能观察到统计结果和变化模式，不能直接证明因果关系。"
            if task_type != "contribution_analysis"
            else "贡献分解仅说明各维度对总体变化的数值贡献，不能确认根本原因。"
        )

        limit_text = "；".join(limitations) if limitations else "当前分析基于单次查询结果，结论范围有限。"
        next_steps = "可以继续按地区、产品、客户或时间等维度拆分验证。"
        if contribution and contribution.get("next_steps"):
            next_steps = contribution["next_steps"][0]

        return {
            "purpose": purpose,
            "observations": observations,
            "evidence": " ".join(evidence_parts),
            "possible_explanations": possible,
            "limitations": limit_text,
            "next_steps": next_steps,
        }

    def _round(self, value: Any) -> Any:
        if isinstance(value, float):
            return round(value, 2)
        return value
