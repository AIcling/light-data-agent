from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from persistence.repositories import MemoryRepository
from workspace.workspace_types import MemoryItem


class SchemaMemoryStore:
    def __init__(self, repo: MemoryRepository) -> None:
        self.repo = repo

    def put_field_alias(
        self,
        project_id: str,
        dataset_id: str,
        alias: str,
        column_name: str,
        source: str = "user_correction",
        confidence: float = 0.95,
    ) -> MemoryItem:
        now = datetime.now(timezone.utc).isoformat()
        item = MemoryItem(
            memory_id=f"mem_{uuid.uuid4().hex[:10]}",
            project_id=project_id,
            dataset_id=dataset_id,
            scope="dataset",
            memory_type="field_alias",
            key=alias,
            value=column_name,
            confidence=confidence,
            source=source,
            created_at=now,
            updated_at=now,
        )
        return self.repo.put(item)

    def get_field_aliases(self, project_id: str, dataset_id: str | None = None) -> dict[str, str]:
        items = self.repo.search(project_id, dataset_id=dataset_id, memory_type="field_alias")
        return {item.key: item.value for item in items}

    def delete_alias(self, memory_id: str) -> None:
        self.repo.delete(memory_id)

    def put_schema_version(
        self,
        project_id: str,
        dataset_id: str,
        schema_summary: dict[str, Any],
        version: int,
    ) -> None:
        import json
        now = datetime.now(timezone.utc).isoformat()
        self.repo.put(
            MemoryItem(
                memory_id=f"mem_{uuid.uuid4().hex[:10]}",
                project_id=project_id,
                dataset_id=dataset_id,
                scope="dataset",
                memory_type="schema_version",
                key=str(version),
                value=json.dumps(schema_summary, ensure_ascii=False, default=str),
                created_at=now,
                updated_at=now,
            )
        )
