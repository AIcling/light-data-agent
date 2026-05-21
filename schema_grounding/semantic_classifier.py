from __future__ import annotations

METRIC_KEYWORDS = ["sales", "sale", "revenue", "amount", "profit", "margin", "quantity", "qty", "price", "cost", "销售", "利润", "数量", "价格", "成本", "收入"]
DIMENSION_KEYWORDS = ["region", "area", "product", "category", "customer", "channel", "type", "地区", "区域", "产品", "类别", "客户", "渠道"]
TIME_KEYWORDS = ["date", "time", "day", "month", "year", "日期", "时间", "月份", "年"]
ID_KEYWORDS = ["id", "uuid", "code", "编号", "编码"]
GEO_KEYWORDS = ["region", "city", "country", "lat", "lon", "geo", "城市", "国家", "经纬"]
CURRENCY_KEYWORDS = ["amount", "price", "cost", "sales", "revenue", "金额", "价格"]
PERCENT_KEYWORDS = ["rate", "ratio", "percent", "pct", "占比", "比例", "率"]
SENSITIVE_KEYWORDS = ["email", "phone", "mobile", "ssn", "password", "address", "身份证", "手机", "邮箱", "地址"]


class SemanticColumnClassifier:
    def classify_role(self, column_name: str, dtype: str, semantic_type: str) -> str:
        lowered = column_name.lower()
        if semantic_type == "time" or any(k in lowered for k in TIME_KEYWORDS):
            return "time"
        if any(k in lowered for k in METRIC_KEYWORDS) and dtype in {"int", "float"}:
            return "metric"
        if semantic_type == "id" or any(k in lowered for k in ID_KEYWORDS):
            return "id"
        if any(k in lowered for k in SENSITIVE_KEYWORDS):
            return "text"
        if any(k in lowered for k in PERCENT_KEYWORDS):
            return "percentage"
        if any(k in lowered for k in CURRENCY_KEYWORDS) and dtype in {"int", "float"}:
            return "currency"
        if any(k in lowered for k in GEO_KEYWORDS):
            return "geo"
        if dtype == "bool":
            return "boolean"
        if semantic_type == "metric" or any(k in lowered for k in METRIC_KEYWORDS):
            return "metric"
        if semantic_type in {"category", "text"} or any(k in lowered for k in DIMENSION_KEYWORDS):
            return "dimension"
        if semantic_type == "text":
            return "text"
        return semantic_type or "unknown"

    def quality_tags(
        self,
        column_name: str,
        dtype: str,
        missing_rate: float,
        unique_count: int,
        row_count: int,
        role: str,
    ) -> list[str]:
        tags: list[str] = []
        if missing_rate >= 0.2:
            tags.append("high_missing")
        if row_count and unique_count / row_count >= 0.9:
            tags.append("high_cardinality")
        if row_count and unique_count == 1:
            tags.append("constant_column")
        if role == "id" or (row_count and unique_count / row_count > 0.95):
            tags.append("likely_identifier")
        if any(k in column_name.lower() for k in SENSITIVE_KEYWORDS):
            tags.append("likely_sensitive")
        if role == "metric" and dtype in {"int", "float"}:
            tags.append("numeric_outlier_possible")
        return tags
