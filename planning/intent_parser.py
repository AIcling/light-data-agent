from __future__ import annotations

import re
from dataclasses import dataclass

from core.types import AnalysisPlan, IntentResult, TableSchema
from memory.memory_store import MemoryStore


METRIC_SYNONYMS = {
    "sales": ["sales", "sale", "revenue", "amount", "销售", "销售额", "营收", "收入"],
    "profit": ["profit", "margin", "利润", "盈利"],
    "quantity": ["quantity", "qty", "volume", "数量", "销量", "件数"],
}


def _contains_any(text: str, keywords: list[str]) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def _column_matches_question(column_name: str, question: str) -> bool:
    lowered_question = question.lower()
    lowered_column = column_name.lower()
    parts = [p for p in re.split(r"[_\W]+", lowered_column) if p]
    if lowered_column in lowered_question:
        return True
    return any(len(part) > 2 and part in lowered_question for part in parts)


@dataclass
class RuleBasedIntentParser:
    def parse(
        self,
        question: str,
        schema: TableSchema,
        memory: MemoryStore | None = None,
    ) -> IntentResult:
        text = question.strip()
        lowered = text.lower()
        task_type = self._detect_task_type(lowered)
        metrics = self._detect_metrics(text, schema)
        dimensions = self._detect_dimensions(text, schema)
        time_columns = self._detect_time_columns(text, schema)
        options = self._detect_options(text)
        filters = self._detect_filters(text, schema)

        session = memory.session if memory else None
        is_follow_up = _contains_any(
            text,
            ["那", "呢", "继续", "换成", "改成", "same", "that", "it", "what about", "只看", "继续往下"],
        )
        if is_follow_up and session is not None:
            if not dimensions and session.last_dimension:
                dimensions = [session.last_dimension]
            if not time_columns and session.last_time_column:
                time_columns = [session.last_time_column]
            if not metrics and session.last_metric:
                metrics = [session.last_metric]
            if task_type == "aggregation" and session.last_task_type:
                task_type = session.last_task_type

        if task_type == "trend" and not time_columns:
            time_columns = schema.likely_time_columns[:1] or [
                c.name for c in schema.columns_by_semantic("time")[:1]
            ]

        if task_type in {"comparison", "ranking", "contribution_analysis", "drill_down"} and not dimensions:
            dimensions = schema.likely_dimensions[:1] or self._default_dimension(schema)

        if task_type not in {"data_quality", "lookup", "report_generation"} and not metrics:
            metrics = schema.likely_metrics[:1] or self._default_metric(schema)

        expected_output = self._expected_output(task_type)
        uncertain = not metrics and task_type not in {"data_quality", "lookup", "report_generation"}

        return IntentResult(
            task_type=task_type,
            metric_candidates=metrics,
            dimension_candidates=dimensions,
            time_column_candidates=time_columns,
            filters=filters,
            expected_output=expected_output,
            options=options,
            uncertain=uncertain,
            notes=[] if not uncertain else ["Could not confidently identify a metric."],
        )

    def _detect_task_type(self, lowered: str) -> str:
        if _contains_any(lowered, ["报告", "report", "汇总报告"]):
            return "report_generation"
        if _contains_any(lowered, ["为什么", "原因", "贡献", "拖累", "导致", "why", "contribution", "contributed"]):
            return "contribution_analysis"
        if _contains_any(lowered, ["往下", "drill", "分解", "细分", "具体情况"]):
            return "drill_down"
        if _contains_any(lowered, ["异常", "outlier", "离群"]):
            return "outlier_detection"
        if _contains_any(lowered, ["缺失", "空值", "重复", "质量", "missing", "null", "duplicate", "quality"]):
            return "data_quality"
        if _contains_any(lowered, ["相关", "关系", "correlation", "relationship"]):
            return "correlation"
        if _contains_any(lowered, ["分布", "histogram", "distribution"]):
            return "distribution"
        if _contains_any(lowered, ["最高", "最低", "最大", "最小", "top", "前", "highest", "lowest", "rank"]):
            return "ranking"
        if _contains_any(lowered, ["趋势", "变化", "每月", "按月", "月份", "每年", "over time", "trend", "monthly", "by month"]):
            return "trend"
        if _contains_any(lowered, ["不同", "各", "比较", "对比", "by ", "per ", "across", "compare"]):
            return "comparison"
        if _contains_any(lowered, ["明细", "列表", "显示", "show", "list"]):
            return "lookup"
        return "aggregation"

    def _detect_filters(self, question: str, schema: TableSchema) -> list[dict]:
        filters: list[dict] = []
        region_match = re.search(r"只看(.{2,10}?)(?:地区|区域)?", question)
        if region_match:
            value = region_match.group(1).strip()
            region_col = next(
                (c.name for c in schema.columns if "region" in c.name.lower() or "地区" in c.aliases),
                schema.likely_dimensions[0] if schema.likely_dimensions else None,
            )
            if region_col and value:
                filters.append({"column": region_col, "operator": "=", "value": value})
        return filters

    def _detect_metrics(self, question: str, schema: TableSchema) -> list[str]:
        matches: list[str] = []
        metric_columns = [
            c for c in schema.columns if c.semantic_type == "metric" or c.dtype in {"int", "float"}
        ]
        for column in metric_columns:
            if _column_matches_question(column.name, question):
                matches.append(column.name)
                continue
            for alias in column.aliases:
                if alias.lower() in question.lower():
                    matches.append(column.name)
                    break
            else:
                lowered_name = column.name.lower()
                for marker, keywords in METRIC_SYNONYMS.items():
                    if marker in lowered_name and _contains_any(question, keywords):
                        matches.append(column.name)
                        break
        return list(dict.fromkeys(matches))

    def _detect_dimensions(self, question: str, schema: TableSchema) -> list[str]:
        matches: list[str] = []
        candidates = [
            c for c in schema.columns if c.semantic_type in {"category", "id", "text"} or c.role == "dimension"
        ]
        for column in candidates:
            if _column_matches_question(column.name, question):
                matches.append(column.name)
                continue
            for alias in column.aliases:
                if alias.lower() in question.lower():
                    matches.append(column.name)
                    break
        if _contains_any(question, ["产品类别", "品类", "category", "product"]):
            for column in candidates:
                if "category" in column.name.lower() or "product" in column.name.lower():
                    matches.append(column.name)
        if _contains_any(question, ["地区", "区域", "region"]):
            for column in candidates:
                if "region" in column.name.lower():
                    matches.append(column.name)
        return list(dict.fromkeys(matches))

    def _detect_time_columns(self, question: str, schema: TableSchema) -> list[str]:
        matches: list[str] = []
        for column in schema.columns_by_semantic("time"):
            if _column_matches_question(column.name, question) or _contains_any(
                question,
                ["每月", "按月", "月份", "日期", "时间", "趋势", "monthly", "month", "date", "trend"],
            ):
                matches.append(column.name)
        return list(dict.fromkeys(matches))

    def _detect_options(self, question: str) -> dict[str, object]:
        options: dict[str, object] = {}
        match = re.search(r"(?:top|前)\s*(\d+)", question, re.IGNORECASE)
        if match:
            options["top_n"] = int(match.group(1))
        elif "前" in question and "为什么" not in question:
            options["top_n"] = 5
        if _contains_any(question, ["折线", "line chart", "line"]):
            options["chart_type"] = "line"
        if _contains_any(question, ["最低", "最小", "lowest", "bottom"]):
            options["sort_direction"] = "asc"
        else:
            options["sort_direction"] = "desc"
        if _contains_any(question, ["平均", "均值", "average", "avg", "mean"]):
            options["aggregation"] = "avg"
        elif _contains_any(question, ["最大", "最高", "max", "highest"]):
            options["aggregation"] = "max"
        elif _contains_any(question, ["最小", "最低", "min", "lowest"]):
            options["aggregation"] = "min"
        elif _contains_any(question, ["数量", "多少条", "count"]):
            options["aggregation"] = "count"
        else:
            options["aggregation"] = "sum"
        return options

    def _default_metric(self, schema: TableSchema) -> list[str]:
        if schema.likely_metrics:
            return [schema.likely_metrics[0]]
        metric_columns = schema.columns_by_semantic("metric")
        if metric_columns:
            return [metric_columns[0].name]
        numeric = [c for c in schema.columns if c.dtype in {"int", "float"}]
        return [numeric[0].name] if numeric else []

    def _default_dimension(self, schema: TableSchema) -> list[str]:
        if schema.likely_dimensions:
            return [schema.likely_dimensions[0]]
        categories = schema.columns_by_semantic("category")
        if categories:
            return [categories[0].name]
        text_columns = schema.columns_by_semantic("text")
        if text_columns:
            return [text_columns[0].name]
        ids = schema.columns_by_semantic("id")
        return [ids[0].name] if ids else []

    def _expected_output(self, task_type: str) -> list[str]:
        mapping = {
            "trend": ["table", "line_chart", "explanation"],
            "comparison": ["table", "bar_chart", "explanation"],
            "ranking": ["table", "bar_chart", "explanation"],
            "distribution": ["table", "histogram", "explanation"],
            "correlation": ["table", "scatter_plot", "explanation"],
            "lookup": ["table", "explanation"],
            "data_quality": ["table", "explanation"],
            "contribution_analysis": ["table", "explanation"],
            "drill_down": ["table", "bar_chart", "explanation"],
            "outlier_detection": ["table", "explanation"],
            "report_generation": ["report", "explanation"],
        }
        return mapping.get(task_type, ["table", "explanation"])
