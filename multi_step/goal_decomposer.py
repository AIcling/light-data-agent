from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from core.types import TableSchema
from memory.memory_store import MemoryStore


MULTI_STEP_PATTERNS = [
    r"为什么.*(?:下降|上升|变化|减少|增加)",
    r"原因是什么",
    r"完整.*报告",
    r"整体.*情况",
    r"全面.*分析",
    r"异常.*解释",
    r"找出.*异常",
    r"数据质量.*诊断",
    r"why did.*(?:drop|decline|increase|change)",
    r"full.*report",
    r"overall.*analysis",
    r"comprehensive",
]

SIMPLE_PATTERNS = [
    r"每个月.*是多少",
    r"哪个.*最高",
    r"哪个.*最低",
    r"前\s*\d+",
    r"有多少",
    r"^show\b",
    r"^list\b",
]


@dataclass
class GoalDecomposer:
    max_steps: int = 6

    def decompose(
        self,
        question: str,
        resolved_query: str,
        schema: TableSchema,
        memory: MemoryStore | None = None,
    ) -> dict[str, Any]:
        text = f"{question} {resolved_query}".lower()
        if any(re.search(p, question, re.IGNORECASE) for p in SIMPLE_PATTERNS):
            if not any(re.search(p, question, re.IGNORECASE) for p in MULTI_STEP_PATTERNS):
                return {
                    "requires_multi_step": False,
                    "reason": "Simple single-query question.",
                    "subgoals": [],
                }

        if ("缺失" in question or "missing" in text) and not any(
            k in question for k in ["质量", "诊断", "怎么样", "如何", "diagnosis"]
        ):
            return {
                "requires_multi_step": False,
                "reason": "Simple missing-value check.",
                "subgoals": [],
            }

        if "报告" in question or "report" in text:
            return {
                "requires_multi_step": True,
                "reason": "User requests a comprehensive report.",
                "plan_type": "report_generation",
                "subgoals": [
                    "Scan dataset schema and quality",
                    "Summarize key metrics",
                    "Identify top dimensions",
                    "Check trends over time",
                    "Synthesize findings and limitations",
                ],
            }

        if any(k in question for k in ["为什么", "原因", "贡献", "下降", "上升", "why", "decline", "drop"]):
            metric = schema.likely_metrics[0] if schema.likely_metrics else "metric"
            return {
                "requires_multi_step": True,
                "reason": "Contribution-style question needs comparison and decomposition.",
                "plan_type": "contribution_analysis",
                "subgoals": [
                    f"Compare recent {metric} with previous period",
                    f"Decompose {metric} change by region",
                    f"Decompose {metric} change by product category",
                    "Summarize observations, limitations, and next steps",
                ],
            }

        if any(k in question for k in ["质量诊断", "数据质量怎么样", "数据质量如何", "quality diagnosis", "全面质量"]):
            return {
                "requires_multi_step": True,
                "reason": "Data quality diagnosis requires multiple checks.",
                "plan_type": "data_quality",
                "subgoals": [
                    "Check missing values across columns",
                    "Check duplicate rows",
                    "Identify high-cardinality and ID columns",
                    "Summarize quality score and recommendations",
                ],
            }

        if any(k in question for k in ["整体", "overview", "概览", "全面", "comprehensive"]):
            return {
                "requires_multi_step": True,
                "reason": "Overview request needs multiple summary steps.",
                "plan_type": "overview",
                "subgoals": [
                    "Preview dataset shape and schema",
                    "Summarize key metrics",
                    "Compare top categories",
                    "Synthesize overview report",
                ],
            }

        return {
            "requires_multi_step": False,
            "reason": "Question can be handled by single-step analysis.",
            "subgoals": [],
        }
