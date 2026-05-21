from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from memory.memory_store import MemoryStore
from planning.followup_planner import FollowUpPlanner
from schema_grounding.alias_manager import AliasManager


@dataclass
class MemoryResolver:
    followup_planner: FollowUpPlanner | None = None
    alias_manager: AliasManager | None = None

    def __post_init__(self) -> None:
        self.followup_planner = self.followup_planner or FollowUpPlanner()
        self.alias_manager = self.alias_manager or AliasManager()

    def resolve(self, question: str, memory: MemoryStore) -> dict[str, Any]:
        text = question.strip()
        session = memory.session
        if not self.followup_planner.is_follow_up(text):
            return self._resolve_with_project_memory(text, memory, direct=True)

        resolved = text
        used_fields: list[str] = []
        resolution_type = "follow_up"
        confidence = 0.78

        if self._is_continue_last(text):
            base = memory.session.last_resolved_query or memory.session.last_question
            if base:
                resolved = base
                used_fields.append("last_resolved_query")
                confidence = 0.85

        elif self._is_metric_swap(text):
            metric = self._detect_metric_swap(text, memory)
            dimension = session.last_dimension or (session.last_dimensions[0] if session.last_dimensions else "")
            if metric and dimension:
                resolved = f"Compare {metric} by {dimension}"
                used_fields.extend(["last_dimension", "last_metric"])
            elif metric:
                resolved = f"Aggregate {metric}"
                used_fields.append("last_task_type")

        elif self._is_dimension_swap(text):
            dimension = self._detect_dimension_swap(text, memory)
            metric = session.last_metric or self._project_metric(memory) or ""
            if "季度" in text or "quarter" in text.lower():
                used_fields.append("preferred_analysis_granularity")
            if dimension and metric:
                resolved = f"Compare {metric} by {dimension}"
                used_fields.extend(["last_metric", "last_dimension", "project_memory"])
            elif dimension:
                resolved = f"Group by {dimension}"
                used_fields.append("last_dimension")

        elif self._is_filter_append(text):
            filter_text = self._extract_filter(text)
            base = session.last_resolved_query or session.last_question
            resolved = f"{base} (filter: {filter_text})"
            used_fields.append("last_resolved_query")

        elif self._is_chart_request(text):
            base = session.last_resolved_query or session.last_question
            resolved = f"{base} (chart: line)"
            used_fields.extend(["last_resolved_query", "last_result_summary"])

        elif self._is_drill_down(text):
            base_dim = session.last_dimension
            resolved = f"Drill down {session.last_metric} by sub-dimension after {base_dim}"
            used_fields.extend(["last_dimension", "last_metric", "last_result_summary"])

        else:
            if session.last_task_type:
                used_fields.append("last_task_type")
            if session.last_metric and "那" in text:
                metric = self._detect_metric_swap(text, memory) or session.last_metric
                dim = session.last_dimension
                resolved = f"Compare {metric} by {dim}" if dim else f"Analyze {metric}"
                used_fields.extend(["last_metric", "last_dimension"])

        result = {
            "resolved_query": resolved,
            "resolution_type": resolution_type,
            "used_memory_fields": used_fields,
            "confidence": confidence if used_fields else 0.5,
        }
        threshold = 0.65
        if result["confidence"] < threshold and resolution_type == "follow_up":
            result["needs_clarification"] = {
                "message": f"系统理解为：{resolved}。如果不对，请补充更明确的指标或维度。",
                "confidence": result["confidence"],
            }
        return result

    def _resolve_with_project_memory(self, text: str, memory: MemoryStore, direct: bool = False) -> dict[str, Any]:
        if memory.project_memory and not direct:
            pass
        return {
            "resolved_query": text,
            "resolution_type": "direct",
            "used_memory_fields": ["project_memory"] if memory.project_memory else [],
            "confidence": 1.0,
        }

    def _project_metric(self, memory: MemoryStore) -> str:
        if memory.project_memory and memory.project_memory.common_metrics:
            return memory.project_memory.common_metrics[0]
        if memory.dataset and memory.dataset.common_metrics:
            return memory.dataset.common_metrics[0]
        return ""

    def _is_continue_last(self, text: str) -> bool:
        return any(k in text for k in ["继续上次", "继续分析", "continue last", "resume"])

    def _is_metric_swap(self, text: str) -> bool:
        return bool(re.search(r"那.*呢|what about", text, re.IGNORECASE))

    def _is_dimension_swap(self, text: str) -> bool:
        return "换成" in text or "改成" in text or "by " in text.lower()

    def _is_filter_append(self, text: str) -> bool:
        return "只看" in text or "filter" in text.lower()

    def _is_chart_request(self, text: str) -> bool:
        return "画" in text or "chart" in text.lower()

    def _is_drill_down(self, text: str) -> bool:
        return "继续" in text or "分解" in text or "细分" in text or "drill" in text.lower()

    def _detect_metric_swap(self, text: str, memory: MemoryStore) -> str:
        schema_cols = memory.dataset.common_metrics if memory.dataset else []
        if not schema_cols and memory.dataset and memory.dataset.schema_summary:
            schema_cols = memory.dataset.schema_summary.get("likely_metrics", [])
        for col in schema_cols:
            for alias in self.alias_manager.build_aliases(col):
                if alias in text:
                    return col
        swaps = {"利润": "profit", "销售": "sales_amount", "数量": "quantity", "营收": "sales_amount"}
        for zh, en in swaps.items():
            if zh in text:
                for col in schema_cols:
                    if en in col.lower():
                        return col
                return en if en in {"profit", "sales_amount", "quantity"} else memory.session.last_metric
        return memory.session.last_metric

    def _detect_dimension_swap(self, text: str, memory: MemoryStore) -> str:
        schema_cols = memory.dataset.common_dimensions if memory.dataset else []
        for col in schema_cols:
            for alias in self.alias_manager.build_aliases(col):
                if alias in text:
                    return col
        if "产品" in text or "类别" in text:
            for col in schema_cols:
                if "product" in col.lower() or "category" in col.lower():
                    return col
        if "月" in text:
            times = memory.dataset.common_time_columns if memory.dataset else []
            return times[0] if times else ""
        return ""

    def _extract_filter(self, text: str) -> str:
        match = re.search(r"只看(.+)", text)
        return match.group(1).strip() if match else text
