from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from persistence.repositories import MemoryRepository
from workspace.workspace_types import MemoryItem


@dataclass
class MetricDefinition:
    name: str
    expression: str
    description: str = ""
    base_column: str = ""
    aggregation: str = "sum"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "expression": self.expression,
            "description": self.description,
            "base_column": self.base_column,
            "aggregation": self.aggregation,
        }


class MetricMemoryStore:
    def __init__(self, repo: MemoryRepository) -> None:
        self.repo = repo

    def put_metric(
        self,
        project_id: str,
        metric: MetricDefinition,
        dataset_id: str | None = None,
        source: str = "user",
    ) -> MemoryItem:
        now = datetime.now(timezone.utc).isoformat()
        return self.repo.put(
            MemoryItem(
                memory_id=f"mem_{uuid.uuid4().hex[:10]}",
                project_id=project_id,
                dataset_id=dataset_id,
                scope="project" if not dataset_id else "dataset",
                memory_type="metric_definition",
                key=metric.name,
                value=json.dumps(metric.to_dict(), ensure_ascii=False),
                source=source,
                confidence=0.95 if source == "user" else 0.7,
                created_at=now,
                updated_at=now,
            )
        )

    def list_metrics(self, project_id: str, dataset_id: str | None = None) -> list[MetricDefinition]:
        items = self.repo.search(project_id, dataset_id=dataset_id, memory_type="metric_definition")
        metrics: list[MetricDefinition] = []
        for item in items:
            data = json.loads(item.value)
            metrics.append(MetricDefinition(**data))
        return metrics

    def resolve_metric_name(self, project_id: str, concept: str, dataset_id: str | None = None) -> str | None:
        lowered = concept.lower()
        for metric in self.list_metrics(project_id, dataset_id):
            if metric.name.lower() == lowered or metric.base_column.lower() == lowered:
                return metric.base_column or metric.name
        aliases = self._alias_items(project_id, dataset_id)
        return aliases.get(concept) or aliases.get(lowered)

    def _alias_items(self, project_id: str, dataset_id: str | None) -> dict[str, str]:
        items = self.repo.search(project_id, dataset_id=dataset_id, memory_type="field_alias")
        return {item.key: item.value for item in items}
