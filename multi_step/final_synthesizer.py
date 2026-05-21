from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from multi_step.multi_step_plan import MultiStepAnalysisPlan, PlanStep


@dataclass
class FinalSynthesizer:
    def synthesize(self, plan: MultiStepAnalysisPlan, step_outputs: dict[str, Any]) -> dict[str, Any]:
        findings: list[str] = []
        limitations: list[str] = []
        evidence: list[str] = []

        for step in plan.steps:
            if step.observations:
                findings.extend(step.observations[:2])
            if step.warnings:
                limitations.extend(step.warnings)
            if step.result_summary and not step.result_summary.get("empty_result"):
                evidence.append(f"{step.goal}: {step.result_summary.get('row_count', 0)} rows")

        contribution = step_outputs.get("contribution_result", {})
        if contribution.get("supported"):
            findings.append(contribution.get("observation", ""))
            limitations.extend(contribution.get("limitations", []))

        quality = step_outputs.get("quality_scan") or step_outputs.get("missing_check")
        if isinstance(quality, dict) and quality.get("quality_score") is not None:
            findings.append(f"Overall data quality score: {quality['quality_score']}/100.")
            limitations.extend(quality.get("recommendations", [])[:2])

        findings = [f for f in findings if f]
        limitations = list(dict.fromkeys([l for l in limitations if l]))

        explanation = self._format_explanation(plan.goal, findings, evidence, limitations)
        return {
            "findings": findings[:10],
            "limitations": limitations[:10],
            "evidence": evidence,
            "explanation": explanation,
            "next_steps": self._next_steps(plan),
        }

    def _format_explanation(self, goal: str, findings: list[str], evidence: list[str], limitations: list[str]) -> str:
        sections = [
            f"分析目标：\n{goal}",
            "主要发现：\n" + ("\n".join(f"- {f}" for f in findings) if findings else "- 暂无足够发现。"),
            "数据证据：\n" + ("\n".join(f"- {e}" for e in evidence) if evidence else "- 各步骤已执行。"),
            "限制：\n" + ("\n".join(f"- {l}" for l in limitations) if limitations else "- 当前分析基于已有字段，不能确认因果原因。"),
            "下一步建议：\n- 可以继续按更细维度 drill-down。\n- 可补充促销、价格等业务字段后再分析。",
        ]
        return "\n\n".join(sections)

    def _next_steps(self, plan: MultiStepAnalysisPlan) -> list[str]:
        if plan.plan_type == "contribution_analysis":
            return ["继续分析贡献最大的地区或品类", "检查数据质量"]
        if plan.plan_type == "data_quality":
            return ["针对高缺失字段做清洗", "重新运行核心指标分析"]
        return ["导出完整报告", "基于发现继续追问"]
