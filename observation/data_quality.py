from __future__ import annotations

from typing import Any

import pandas as pd


class DataQualityAnalyzer:
    MISSING_THRESHOLD = 0.2
    HIGH_CARDINALITY_RATIO = 0.9

    def analyze(self, df: pd.DataFrame, schema_summary: dict[str, Any] | None = None) -> dict[str, Any]:
        issues: list[dict[str, Any]] = []
        recommendations: list[str] = []
        columns_meta = {}
        if schema_summary:
            columns_meta = {c["name"]: c for c in schema_summary.get("columns", [])}

        duplicate_count = int(df.duplicated().sum())
        if duplicate_count > 0:
            issues.append({
                "type": "duplicate_row",
                "column": None,
                "severity": "medium",
                "message": f"检测到 {duplicate_count} 行完全重复记录。",
            })
            recommendations.append("分析前可考虑去重，避免重复记录影响聚合结果。")

        for column in df.columns:
            series = df[column]
            missing_rate = float(series.isna().mean())
            unique_count = int(series.nunique(dropna=True))
            row_count = max(len(df), 1)
            unique_ratio = unique_count / row_count
            meta = columns_meta.get(str(column), {})

            if missing_rate >= self.MISSING_THRESHOLD:
                issues.append({
                    "type": "missing_value",
                    "column": str(column),
                    "severity": "medium" if missing_rate < 0.5 else "high",
                    "message": f"{column} 字段缺失率为 {missing_rate:.1%}。",
                })
                recommendations.append(f"分析 {column} 时需要注意缺失值影响。")

            if unique_ratio >= self.HIGH_CARDINALITY_RATIO and row_count > 10:
                issues.append({
                    "type": "high_cardinality",
                    "column": str(column),
                    "severity": "info",
                    "message": f"{column} 唯一值比例较高，可能是 ID 字段。",
                })
                recommendations.append(f"{column} 不建议直接作为类别维度进行柱状图展示。")

            if unique_count == 1 and row_count > 1:
                issues.append({
                    "type": "constant_column",
                    "column": str(column),
                    "severity": "info",
                    "message": f"{column} 为常量列，没有分析价值。",
                })

            if pd.api.types.is_numeric_dtype(series):
                q1, q3 = series.quantile(0.25), series.quantile(0.75)
                iqr = q3 - q1
                if iqr > 0:
                    outliers = series[(series < q1 - 1.5 * iqr) | (series > q3 + 1.5 * iqr)]
                    if len(outliers) > 0:
                        issues.append({
                            "type": "outlier",
                            "column": str(column),
                            "severity": "info",
                            "message": f"{column} 可能存在 {len(outliers)} 个异常值（IQR 方法）。",
                        })

            if "likely_sensitive" in meta.get("quality_tags", []):
                issues.append({
                    "type": "sensitive_column",
                    "column": str(column),
                    "severity": "warning",
                    "message": f"{column} 可能是敏感字段。",
                })

        quality_score = max(0, 100 - len(issues) * 8 - duplicate_count)
        return {
            "quality_score": quality_score,
            "issues": issues,
            "recommendations": list(dict.fromkeys(recommendations))[:6],
        }
