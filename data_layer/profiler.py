from __future__ import annotations

import pandas as pd

from core.types import TableSchema
from data_layer.schema_extractor import SchemaExtractor


class DataProfiler:
    def __init__(self, schema_extractor: SchemaExtractor | None = None) -> None:
        self.schema_extractor = schema_extractor or SchemaExtractor()

    def profile(self, df: pd.DataFrame, table_name: str) -> TableSchema:
        return self.schema_extractor.extract(df, table_name)
