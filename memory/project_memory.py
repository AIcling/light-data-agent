from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from persistence.repositories import MemoryRepository
from workspace.workspace_types import MemoryItem


@dataclass
class ProjectMemory:
    project_id: str = ""
    project_goal: str = ""
    domain: str = ""
    common_metrics: list[str] = field(default_factory=list)
    common_dimensions: list[str] = field(default_factory=list)
    common_time_columns: list[str] = field(default_factory=list)
    preferred_analysis_granularity: str = "month"
    known_limitations: list[str] = field(default_factory=list)
    important_findings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "project_goal": self.project_goal,
            "domain": self.domain,
            "common_metrics": self.common_metrics,
            "common_dimensions": self.common_dimensions,
            "common_time_columns": self.common_time_columns,
            "preferred_analysis_granularity": self.preferred_analysis_granularity,
            "known_limitations": self.known_limitations,
            "important_findings": self.important_findings,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProjectMemory":
        return cls(
            project_id=data.get("project_id", ""),
            project_goal=data.get("project_goal", ""),
            domain=data.get("domain", ""),
            common_metrics=list(data.get("common_metrics", [])),
            common_dimensions=list(data.get("common_dimensions", [])),
            common_time_columns=list(data.get("common_time_columns", [])),
            preferred_analysis_granularity=data.get("preferred_analysis_granularity", "month"),
            known_limitations=list(data.get("known_limitations", [])),
            important_findings=list(data.get("important_findings", [])),
        )


class ProjectMemoryStore:
    MEMORY_TYPE = "project_context"

    def __init__(self, repo: MemoryRepository) -> None:
        self.repo = repo

    def load(self, project_id: str) -> ProjectMemory:
        item = self.repo.get(project_id, "project", self.MEMORY_TYPE, "context")
        if item:
            import json
            return ProjectMemory.from_dict(json.loads(item.value))
        return ProjectMemory(project_id=project_id)

    def save(self, memory: ProjectMemory) -> None:
        import json
        now = datetime.now(timezone.utc).isoformat()
        self.repo.put(
            MemoryItem(
                memory_id=f"mem_{uuid.uuid4().hex[:10]}",
                project_id=memory.project_id,
                scope="project",
                memory_type=self.MEMORY_TYPE,
                key="context",
                value=json.dumps(memory.to_dict(), ensure_ascii=False),
                confidence=1.0,
                source="system",
                created_at=now,
                updated_at=now,
            )
        )

    def add_finding(self, project_id: str, finding: str) -> None:
        memory = self.load(project_id)
        if finding not in memory.important_findings:
            memory.important_findings.append(finding)
            memory.important_findings = memory.important_findings[-20:]
        self.save(memory)

    def update_from_schema(self, project_id: str, schema_summary: dict) -> None:
        memory = self.load(project_id)
        memory.project_id = project_id
        metrics = schema_summary.get("likely_metrics", [])
        dims = schema_summary.get("likely_dimensions", [])
        times = schema_summary.get("likely_time_columns", [])
        memory.common_metrics = list(dict.fromkeys(memory.common_metrics + metrics))[:10]
        memory.common_dimensions = list(dict.fromkeys(memory.common_dimensions + dims))[:10]
        memory.common_time_columns = list(dict.fromkeys(memory.common_time_columns + times))[:5]
        self.save(memory)
