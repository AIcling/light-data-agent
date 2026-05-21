from __future__ import annotations

import time

import duckdb
import pandas as pd

from core.types import ExecutionResult
from sql_layer.utils import quote_identifier, strip_trailing_semicolon


class QueryEngine:
    def __init__(self, max_result_rows: int = 100) -> None:
        self.connection = duckdb.connect(database=":memory:")
        self.max_result_rows = max_result_rows
        self.registered_tables: set[str] = set()

    def register_dataframe(self, table_name: str, df: pd.DataFrame) -> None:
        self.connection.register(table_name, df)
        self.registered_tables.add(table_name)

    def explain(self, sql: str) -> None:
        self.connection.execute(f"EXPLAIN {strip_trailing_semicolon(sql)}")

    def execute(self, sql: str) -> ExecutionResult:
        start = time.perf_counter()
        try:
            final_sql = self._ensure_limit(sql)
            df = self.connection.execute(final_sql).fetchdf()
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            return ExecutionResult(
                status="success",
                dataframe=df,
                row_count=int(len(df)),
                execution_time_ms=elapsed_ms,
                columns=[str(c) for c in df.columns],
            )
        except Exception as exc:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            return ExecutionResult(
                status="error",
                dataframe=pd.DataFrame(),
                row_count=0,
                execution_time_ms=elapsed_ms,
                columns=[],
                error=str(exc),
            )

    def table_preview_sql(self, table_name: str, rows: int = 10) -> str:
        return f"SELECT * FROM {quote_identifier(table_name)} LIMIT {rows}"

    def _ensure_limit(self, sql: str) -> str:
        cleaned = strip_trailing_semicolon(sql)
        if " limit " in f" {cleaned.lower()} ":
            return cleaned
        return f"{cleaned} LIMIT {self.max_result_rows}"
