from __future__ import annotations

from sql_layer.validator import SQLValidator


def test_validator_accepts_valid_select(sample_schema, query_engine):
    validator = SQLValidator(query_engine=query_engine, max_result_rows=100)
    result = validator.validate(
        'SELECT "region", SUM("sales_amount") AS total_sales FROM "sales" GROUP BY "region"',
        sample_schema,
    )
    assert result.valid
    assert result.normalized_sql is not None
    assert "LIMIT" in result.normalized_sql.upper()


def test_validator_rejects_dangerous_sql(sample_schema, query_engine):
    validator = SQLValidator(query_engine=query_engine)
    result = validator.validate("DROP TABLE sales", sample_schema)
    assert not result.valid
    assert any("Dangerous keyword" in error for error in result.errors)


def test_validator_rejects_unknown_column(sample_schema, query_engine):
    validator = SQLValidator(query_engine=query_engine)
    result = validator.validate('SELECT SUM("sales") FROM "sales"', sample_schema)
    assert not result.valid
    assert any("sales_amount" in error for error in result.errors)
