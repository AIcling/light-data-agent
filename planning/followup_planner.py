from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from memory.memory_store import MemoryStore


@dataclass
class FollowUpPlanner:
    FOLLOW_UP_MARKERS = ["那", "呢", "继续", "换成", "改成", "只看", "what about", "same", "that", "it", "继续往下", "画成"]

    def suggest(self, task_type: str, schema_summary: dict[str, Any]) -> list[str]:
        metrics = schema_summary.get("likely_metrics", [])
        dimensions = schema_summary.get("likely_dimensions", [])
        suggestions: list[str] = []
        if task_type == "comparison" and metrics and dimensions:
            other_metrics = [m for m in metrics if m != metrics[0]]
            if other_metrics:
                suggestions.append(f"那 {other_metrics[0]} 呢？")
            suggestions.append(f"换成按 {dimensions[-1] if len(dimensions) > 1 else '月份'} 看")
        elif task_type == "trend" and dimensions:
            suggestions.append(f"按 {dimensions[0]} 拆分趋势")
        elif task_type == "ranking" and dimensions:
            suggestions.append(f"看一下排名第一的 {dimensions[0]} 的详细分解")
        suggestions.append("数据里有没有缺失值？")
        if metrics:
            suggestions.append(f"哪个 {dimensions[0] if dimensions else '维度'} 的 {metrics[0]} 最高？")
        return suggestions[:4]

    def is_follow_up(self, question: str) -> bool:
        text = question.strip()
        return any(marker in text.lower() or marker in text for marker in self.FOLLOW_UP_MARKERS)
