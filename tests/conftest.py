from __future__ import annotations

from pathlib import Path

import pytest

from data_layer.loader import CSVLoader
from schema_grounding.schema_extractor import EnhancedSchemaExtractor as SchemaExtractor
from sql_layer.executor import QueryEngine


@pytest.fixture()
def sample_dataset():
    return CSVLoader().load(Path("sample_data/sales.csv"), table_name="sales")


@pytest.fixture()
def sample_schema(sample_dataset):
    return SchemaExtractor().extract(sample_dataset.dataframe, sample_dataset.table_name)


@pytest.fixture()
def query_engine(sample_dataset):
    engine = QueryEngine(max_result_rows=100)
    engine.register_dataframe(sample_dataset.table_name, sample_dataset.dataframe)
    return engine
