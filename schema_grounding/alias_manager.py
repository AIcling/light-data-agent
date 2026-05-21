from __future__ import annotations

from schema_grounding.semantic_classifier import (
    CURRENCY_KEYWORDS,
    DIMENSION_KEYWORDS,
    METRIC_KEYWORDS,
    TIME_KEYWORDS,
)


DEFAULT_ALIASES: dict[str, list[str]] = {
    "sales_amount": ["sales", "sale", "revenue", "amount", "销售", "销售额", "营收", "收入"],
    "profit": ["profit", "margin", "利润", "盈利"],
    "quantity": ["quantity", "qty", "volume", "数量", "销量", "件数"],
    "price": ["price", "单价", "价格"],
    "cost": ["cost", "成本"],
    "region": ["region", "area", "地区", "区域"],
    "product_category": ["product", "category", "产品", "品类", "类别"],
    "customer_id": ["customer", "client", "客户"],
    "order_date": ["date", "month", "year", "日期", "月份", "月", "年"],
}


class AliasManager:
    def __init__(self, known_aliases: dict[str, list[str]] | None = None) -> None:
        self.known_aliases = known_aliases or {}

    def build_aliases(self, column_name: str, original_name: str = "") -> list[str]:
        aliases = list(self.known_aliases.get(column_name, DEFAULT_ALIASES.get(column_name, [])))
        if original_name and original_name != column_name:
            aliases.append(original_name)
        parts = [p for p in column_name.replace("_", " ").split() if len(p) > 1]
        aliases.extend(parts)
        return list(dict.fromkeys(aliases))

    def resolve_column(self, concept: str, column_names: list[str]) -> str | None:
        lowered = concept.lower().strip()
        for name in column_names:
            if name.lower() == lowered:
                return name
        for name in column_names:
            aliases = self.build_aliases(name)
            if any(lowered == alias.lower() or lowered in alias.lower() for alias in aliases):
                return name
            if lowered in name.lower():
                return name
        return None

    def concept_in_schema(self, concept: str, column_names: list[str]) -> bool:
        return self.resolve_column(concept, column_names) is not None

    def to_memory_aliases(self, column_names: list[str]) -> dict[str, str]:
        mapping: dict[str, str] = {}
        for name in column_names:
            for alias in self.build_aliases(name):
                mapping[alias] = name
        return mapping
