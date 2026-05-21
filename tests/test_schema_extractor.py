from __future__ import annotations


def test_schema_extractor_detects_core_metadata(sample_schema):
    assert sample_schema.table_name == "sales"
    assert sample_schema.row_count > 0
    assert "order_date" in sample_schema.column_names
    assert "sales_amount" in sample_schema.column_names

    order_date = sample_schema.get_column("order_date")
    sales_amount = sample_schema.get_column("sales_amount")
    region = sample_schema.get_column("region")

    assert order_date is not None
    assert order_date.semantic_type == "time"
    assert sales_amount is not None
    assert sales_amount.semantic_type == "metric"
    assert sales_amount.min_value is not None
    assert sales_amount.max_value is not None
    assert region is not None
    assert region.semantic_type == "category"
