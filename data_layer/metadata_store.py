from __future__ import annotations

from dataclasses import dataclass, field

from core.types import TableSchema


@dataclass
class MetadataStore:
    schemas: dict[str, TableSchema] = field(default_factory=dict)

    def put_schema(self, schema: TableSchema) -> None:
        self.schemas[schema.table_name] = schema

    def get_schema(self, table_name: str) -> TableSchema | None:
        return self.schemas.get(table_name)

    def clear(self) -> None:
        self.schemas.clear()
