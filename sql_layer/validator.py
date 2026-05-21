from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from typing import Iterable

from core.types import AnalysisPlan, TableSchema, ValidationLayerResult, ValidationResult
from safety.policy import validate_policy
from sql_layer.executor import QueryEngine
from sql_layer.utils import strip_trailing_semicolon

try:
    import sqlglot
    from sqlglot import exp
except ImportError:  # pragma: no cover
    sqlglot = None
    exp = None


@dataclass
class SQLValidator:
    query_engine: QueryEngine | None = None
    max_result_rows: int = 100
    allow_write_sql: bool = False

    def validate(
        self,
        sql: str,
        schema: TableSchema,
        analysis_plan: AnalysisPlan | None = None,
    ) -> ValidationResult:
        cleaned = strip_trailing_semicolon(sql)
        if not cleaned:
            return self._deny(["SQL is empty."])

        policy_errors, policy_warnings = validate_policy(cleaned, self.allow_write_sql)
        policy = ValidationLayerResult(passed=not policy_errors, errors=policy_errors, warnings=policy_warnings)

        syntax_errors: list[str] = []
        syntax_warnings: list[str] = []
        parsed = None
        if sqlglot is not None:
            try:
                parsed_statements = sqlglot.parse(cleaned, read="duckdb")
                if len(parsed_statements) != 1:
                    syntax_errors.append("Only one SQL statement is allowed.")
                else:
                    parsed = parsed_statements[0]
                    syntax_errors.extend(self._validate_statement_type(parsed))
            except Exception as exc:
                syntax_errors.append(f"SQL parse error: {exc}")
        else:
            syntax_warnings.append("sqlglot is not installed; using limited validation.")
            if not cleaned.lower().startswith("select"):
                syntax_errors.append("Only SELECT queries are allowed.")
        syntax = ValidationLayerResult(
            passed=not syntax_errors, errors=syntax_errors, warnings=syntax_warnings
        )

        schema_errors: list[str] = []
        schema_suggestions: list[dict] = []
        if parsed is not None:
            schema_errors, schema_suggestions = self._validate_schema_with_suggestions(parsed, schema)
        schema_layer = ValidationLayerResult(
            passed=not schema_errors,
            errors=schema_errors,
            suggestions=schema_suggestions,
        )

        semantic_warnings = self._semantic_validation(cleaned, analysis_plan)
        semantic = ValidationLayerResult(passed=True, warnings=semantic_warnings)

        normalized_sql = self._with_limit(cleaned)
        dry_run_errors: list[str] = []
        if (
            policy.passed
            and syntax.passed
            and schema_layer.passed
            and self.query_engine is not None
        ):
            try:
                self.query_engine.explain(normalized_sql)
            except Exception as exc:
                dry_run_errors.append(f"DuckDB dry-run failed: {exc}")
        dry_run = ValidationLayerResult(passed=not dry_run_errors, errors=dry_run_errors)

        all_errors = policy_errors + syntax_errors + schema_errors + dry_run_errors
        valid = not all_errors
        return ValidationResult(
            valid=valid,
            errors=all_errors,
            warnings=policy_warnings + syntax_warnings + semantic_warnings,
            normalized_sql=normalized_sql,
            policy=policy,
            syntax=syntax,
            schema=schema_layer,
            semantic=semantic,
            dry_run=dry_run,
            final_decision="allow" if valid else "deny",
        )

    def _deny(self, errors: list[str]) -> ValidationResult:
        return ValidationResult(
            valid=False,
            errors=errors,
            policy=ValidationLayerResult(False, errors),
            final_decision="deny",
        )

    def _validate_statement_type(self, parsed) -> list[str]:
        if exp is None:
            return []
        if isinstance(parsed, (exp.Select, exp.Union, exp.With)):
            return []
        if parsed.find(exp.Select) is not None and parsed.key in {"with", "select"}:
            return []
        return ["Only SELECT queries are allowed."]

    def _validate_schema_with_suggestions(
        self, parsed, schema: TableSchema
    ) -> tuple[list[str], list[dict]]:
        if exp is None:
            return [], []
        errors: list[str] = []
        suggestions: list[dict] = []
        allowed_tables = {schema.table_name.lower()}
        allowed_columns = {column.lower() for column in schema.column_names}
        aliases = self._select_aliases(parsed)

        for table in parsed.find_all(exp.Table):
            table_name = table.name.lower()
            if table_name not in allowed_tables:
                suggestion = self._closest(table.name, [schema.table_name])
                extra = f" Did you mean '{suggestion}'?" if suggestion else ""
                errors.append(f"Table '{table.name}' does not exist.{extra}")
                suggestions.append({"missing_table": table.name, "suggestions": [suggestion] if suggestion else []})

        for column in parsed.find_all(exp.Column):
            column_name = column.name
            if column_name == "*":
                continue
            lowered = column_name.lower()
            if lowered in allowed_columns or lowered in aliases:
                continue
            suggestion = self._closest(column_name, schema.column_names)
            extra = f" Did you mean '{suggestion}'?" if suggestion else ""
            errors.append(f"Column '{column_name}' does not exist.{extra}")
            suggestions.append(
                {"missing_column": column_name, "suggestions": [suggestion] if suggestion else []}
            )
        return list(dict.fromkeys(errors)), suggestions

    def _semantic_validation(self, sql: str, plan: AnalysisPlan | None) -> list[str]:
        if plan is None:
            return []
        warnings: list[str] = []
        upper = sql.upper()
        task = plan.task_type
        if task == "trend" and "STRFTIME" not in upper and "DATE_TRUNC" not in upper and "GROUP BY" in upper:
            warnings.append("Trend task may benefit from explicit time bucketing.")
        if task == "ranking" and "ORDER BY" not in upper:
            warnings.append("Ranking task should include ORDER BY.")
        if task in {"comparison", "ranking", "aggregation"} and "GROUP BY" not in upper and "SUM(" not in upper and "AVG(" not in upper:
            if task != "aggregation":
                warnings.append("Comparison/ranking task may need GROUP BY.")
        metrics = plan.data_requirements.get("metrics", []) if plan.data_requirements else []
        agg = str(metrics[0]) if metrics else ""
        if ("平均" in plan.goal or plan.data_requirements.get("aggregation") == "avg") and agg:
            if "AVG(" not in upper:
                warnings.append("User asked for average but SQL may not use AVG.")
        return warnings

    def _select_aliases(self, parsed) -> set[str]:
        if exp is None:
            return set()
        aliases: set[str] = set()
        for select in parsed.find_all(exp.Select):
            for expression in select.expressions:
                alias = expression.alias
                if alias:
                    aliases.add(alias.lower())
        return aliases

    def _closest(self, name: str, candidates: Iterable[str]) -> str | None:
        matches = difflib.get_close_matches(name, list(candidates), n=1, cutoff=0.55)
        return matches[0] if matches else None

    def _with_limit(self, sql: str) -> str:
        cleaned = strip_trailing_semicolon(sql)
        if re.search(r"\blimit\b", cleaned, flags=re.IGNORECASE):
            return cleaned
        return f"{cleaned} LIMIT {self.max_result_rows}"
