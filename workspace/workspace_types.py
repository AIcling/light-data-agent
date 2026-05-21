from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Project:
    project_id: str
    name: str
    description: str = ""
    active_dataset_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DatasetRecord:
    dataset_id: str
    project_id: str
    name: str
    source_type: str = "csv"
    file_path: str = ""
    file_hash: str = ""
    table_name: str = ""
    row_count: int = 0
    column_count: int = 0
    schema_version: int = 1
    schema_json: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_now)
    last_used_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ArtifactRecord:
    artifact_id: str
    project_id: str
    artifact_type: str
    name: str
    analysis_id: str | None = None
    path: str = ""
    content: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AnalysisRecord:
    analysis_id: str
    project_id: str
    user_query: str
    status: str
    dataset_id: str | None = None
    resolved_query: str = ""
    task_type: str = ""
    goal: str = ""
    main_findings: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MemoryItem:
    memory_id: str
    project_id: str
    scope: str
    memory_type: str
    key: str
    value: str
    dataset_id: str | None = None
    confidence: float = 1.0
    source: str = "system"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    expires_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
