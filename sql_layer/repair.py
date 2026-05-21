from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

from core.types import AnalysisPlan, RepairResult, TableSchema
from sql_layer.utils import strip_trailing_semicolon

try:
    import sqlglot
    from sqlglot import exp
except ImportError:  # pragma: no cover
    sqlglot = None
    exp = None


@dataclass
class SQLRepairer:
    def repair(
        self,
        question: str,
        sql: str,
        errors: list[str],
        schema: TableSchema,
        analysis_plan: AnalysisPlan | None = None,
        repair_attempt: int = 1,
    ) -> str:
        return self.repair_with_result(
            question, sql, errors, schema, analysis_plan, repair_attempt
        ).sql

    def repair_with_result(
        self,
        question: str,
        sql: str,
        errors: list[str],
        schema: TableSchema,
        analysis_plan: AnalysisPlan | None = None,
        repair_attempt: int = 1,
    ) -> RepairResult:
        actions: list[str] = []
        repaired = strip_trailing_semicolon(sql)

        for error in errors:
            if any(kw in error.upper() for kw in ("DROP", "DELETE", "UPDATE", "INSERT")):
                return RepairResult(repaired=False, sql=sql, repair_actions=["Dangerous SQL cannot be repaired."], confidence=0.0)

        new_sql, error_actions = self._repair_from_error_messages(repaired, errors, schema)
        repaired = new_sql
        actions.extend(error_actions)

        new_sql, parse_actions = self._repair_by_parsing(repaired, schema)
        repaired = new_sql
        actions.extend(parse_actions)

        new_sql, duckdb_actions = self._repair_duckdb_dialect(repaired)
        repaired = new_sql
        actions.extend(duckdb_actions)

        if not re.search(r"\blimit\b", repaired, re.IGNORECASE):
            repaired = f"{repaired} LIMIT 100"
            actions.append("Added missing LIMIT clause.")

        confidence = 0.82 if actions else 0.0
        return RepairResult(
            repaired=bool(actions),
            sql=repaired,
            repair_actions=actions,
            confidence=confidence,
        )

    def _repair_from_error_messages(
        self, sql: str, errors: list[str], schema: TableSchema
    ) -> tuple[str, list[str]]:
        repaired = sql
        actions: list[str] = []
        for error in errors:
            for kind, candidates in (
                ("Column", schema.column_names),
                ("Table", [schema.table_name]),
            ):
                match = re.search(rf"{kind} '([^']+)' does not exist", error)
                if not match:
                    continue
                bad_name = match.group(1)
                replacement = self._closest(bad_name, candidates)
                if replacement:
                    repaired = self._replace_identifier(repaired, bad_name, replacement)
                    actions.append(f"Replaced missing {kind.lower()} {bad_name} with {replacement}.")
                elif kind == "Table":
                    repaired = self._replace_identifier(repaired, bad_name, schema.table_name)
                    actions.append(f"Replaced table {bad_name} with {schema.table_name}.")
        return repaired, actions

    def _repair_by_parsing(self, sql: str, schema: TableSchema) -> tuple[str, list[str]]:
        if sqlglot is None or exp is None:
            return sql, []
        actions: list[str] = []
        try:
            parsed = sqlglot.parse_one(sql, read="duckdb")
        except Exception:
            return sql, actions
        repaired = sql
        allowed_columns = {name.lower(): name for name in schema.column_names}
        for table in parsed.find_all(exp.Table):
            if table.name.lower() != schema.table_name.lower():
                repaired = self._replace_identifier(repaired, table.name, schema.table_name)
                actions.append(f"Fixed table name {table.name} -> {schema.table_name}.")
        for column in parsed.find_all(exp.Column):
            if column.name == "*" or column.name.lower() in allowed_columns:
                continue
            replacement = self._closest(column.name, schema.column_names)
            if replacement:
                repaired = self._replace_identifier(repaired, column.name, replacement)
                actions.append(f"Fixed column {column.name} -> {replacement}.")
        return repaired, actions

    def _repair_duckdb_dialect(self, sql: str) -> tuple[str, list[str]]:
        actions: list[str] = []
        repaired = sql
        if re.search(r"\bmonth\s*\(", repaired, re.IGNORECASE):
            repaired = re.sub(
                r"month\s*\(\s*([^)]+)\s*\)",
                r"strftime(CAST(\1 AS TIMESTAMP), '%Y-%m')",
                repaired,
                flags=re.IGNORECASE,
            )
            actions.append("Replaced month() with DuckDB-compatible strftime.")
        if re.search(r"\byear\s*\(", repaired, re.IGNORECASE):
            repaired = re.sub(
                r"year\s*\(\s*([^)]+)\s*\)",
                r"strftime(CAST(\1 AS TIMESTAMP), '%Y')",
                repaired,
                flags=re.IGNORECASE,
            )
            actions.append("Replaced year() with DuckDB-compatible strftime.")
        return repaired, actions

    def _closest(self, name: str, candidates: list[str]) -> str | None:
        matches = difflib.get_close_matches(name, candidates, n=1, cutoff=0.45)
        return matches[0] if matches else None

    def _replace_identifier(self, sql: str, old: str, new: str) -> str:
        escaped_old = re.escape(old)
        sql = re.sub(rf'"{escaped_old}"', f'"{new}"', sql)
        return re.sub(rf"\b{escaped_old}\b", new, sql)
