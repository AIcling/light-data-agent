from __future__ import annotations

import re
from typing import Any

from core.types import TableSchema
from schema_grounding.alias_manager import AliasManager


CAUSAL_PATTERNS = [
    r"为什么.*(?:下降|上升|变化|增长|减少)",
    r"原因是什么",
    r"what caused",
    r"why did.*(?:drop|increase|change|decline)",
]

PREDICTION_PATTERNS = [
    r"预测",
    r"forecast",
    r"predict",
    r"未来",
    r"next month",
    r"下月",
]

EXTERNAL_CONCEPTS = [
    "promotion", "campaign", "discount", "促销", "活动", "折扣", "优惠券",
    "inventory", "库存", "weather", "天气", "competitor", "竞争对手",
    "channel", "渠道", "stock", "股价",
]


class CannotAnswerDetector:
    def __init__(self, alias_manager: AliasManager | None = None) -> None:
        self.alias_manager = alias_manager or AliasManager()

    def detect(self, question: str, schema: TableSchema, task_type: str = "") -> dict[str, Any] | None:
        lowered = question.lower()
        column_names = schema.column_names

        if any(re.search(p, question, re.IGNORECASE) for p in PREDICTION_PATTERNS):
            return self._result(
                "当前系统未启用预测/建模模块，无法回答预测类问题。",
                self._alternatives(schema),
            )

        missing_external = [
            concept for concept in EXTERNAL_CONCEPTS
            if concept.lower() in lowered and not self.alias_manager.concept_in_schema(concept, column_names)
        ]
        if missing_external and task_type not in {"contribution_analysis", "trend", "comparison"}:
            concepts = "、".join(missing_external[:5])
            return self._result(
                f"当前数据中没有 {concepts} 相关字段，无法直接分析该概念。",
                self._alternatives(schema),
            )

        mentioned_missing = self._find_missing_mentioned_fields(question, column_names)
        if mentioned_missing:
            names = "、".join(mentioned_missing)
            return self._result(
                f"当前 Schema 中不存在字段或概念：{names}。",
                self._alternatives(schema),
            )

        if task_type == "correlation" and len(schema.likely_metrics) < 2:
            return self._result(
                "当前数据至少需要两个数值指标才能做相关性分析。",
                self._alternatives(schema),
            )

        return None

    def _find_missing_mentioned_fields(self, question: str, column_names: list[str]) -> list[str]:
        tokens = re.findall(r"[\u4e00-\u9fff]+|[a-zA-Z_][a-zA-Z0-9_]*", question)
        missing: list[str] = []
        skip = {"那", "呢", "的", "是", "什么", "多少", "怎么", "哪些", "有没有", "数据", "分析", "查看", "显示"}
        for token in tokens:
            if token.lower() in skip or len(token) < 2:
                continue
            if token.lower() in {"sql", "chart", "table", "limit", "select", "from", "group", "order"}:
                continue
            if self.alias_manager.concept_in_schema(token, column_names):
                continue
            if any(token.lower() in name.lower() for name in column_names):
                continue
            if token in {"销售", "利润", "地区", "类别", "月份", "趋势", "排名", "平均", "最高", "最低"}:
                continue
            if re.match(r"^[\u4e00-\u9fff]+$", token) and len(token) <= 2:
                continue
            if token.endswith("吗") or token.endswith("呢"):
                continue
        return missing

    def _alternatives(self, schema: TableSchema) -> list[str]:
        alts: list[str] = []
        if schema.likely_time_columns and schema.likely_metrics:
            alts.append(f"可以分析 {schema.likely_metrics[0]} 随时间的变化")
        if schema.likely_dimensions and schema.likely_metrics:
            alts.append(
                f"可以按 {schema.likely_dimensions[0]} 拆分 {schema.likely_metrics[0]}"
            )
        alts.append("可以检查数据缺失值和重复情况")
        if schema.likely_metrics:
            alts.append(f"可以查看 {schema.likely_metrics[0]} 的排名或分布")
        return alts[:4]

    def _result(self, reason: str, alternatives: list[str]) -> dict[str, Any]:
        return {
            "cannot_answer": True,
            "reason": reason,
            "available_alternatives": alternatives,
        }
