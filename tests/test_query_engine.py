from __future__ import annotations


def test_query_engine_executes_duckdb_sql(query_engine):
    result = query_engine.execute(
        'SELECT "region", SUM("sales_amount") AS total_sales '
        'FROM "sales" GROUP BY "region" ORDER BY total_sales DESC LIMIT 10'
    )
    assert result.status == "success"
    assert result.row_count > 0
    assert {"region", "total_sales"}.issubset(set(result.columns))
