from __future__ import annotations

import hashlib
import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from core.types import TableSchema
from persistence.repositories import (
    AnalysisRepository,
    ArtifactRepository,
    DatasetRepository,
    MemoryRepository,
    ProjectRepository,
)
from persistence.sqlite_store import SQLiteStore
from workspace.artifact_store import ArtifactStore
from workspace.dataset_registry import DatasetRegistry
from workspace.workspace_types import AnalysisRecord, ArtifactRecord, Project


class ProjectManager:
    def __init__(
        self,
        storage_dir: str | Path = "storage/projects",
        db_path: str | Path = "storage/data_agent.db",
    ) -> None:
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.store = SQLiteStore(db_path)
        self.projects = ProjectRepository(self.store)
        self.datasets = DatasetRepository(self.store)
        self.memory_repo = MemoryRepository(self.store)
        self.analyses = AnalysisRepository(self.store)
        self.artifacts = ArtifactRepository(self.store)
        self.dataset_registry = DatasetRegistry(self.datasets, self.storage_dir)
        self.artifact_store = ArtifactStore(self.artifacts, self.storage_dir)

    def ensure_default_project(self, default_name: str = "Default Project") -> Project:
        existing = self.projects.list_projects()
        if existing:
            return existing[0]
        return self.create_project(default_name, "Auto-created default workspace")

    def create_project(self, name: str, description: str = "", metadata: dict | None = None) -> Project:
        project = self.projects.create(name, description, metadata)
        project_dir = self.storage_dir / project.project_id
        for sub in ("datasets", "schemas", "memory", "analyses", "reports", "artifacts", "logs"):
            (project_dir / sub).mkdir(parents=True, exist_ok=True)
        project_meta = project_dir / "project.json"
        project_meta.write_text(json.dumps(project.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return project

    def list_projects(self) -> list[Project]:
        return self.projects.list_projects()

    def get_project(self, project_id: str) -> Project | None:
        return self.projects.get(project_id)

    def rename_project(self, project_id: str, name: str) -> Project | None:
        project = self.projects.get(project_id)
        if not project:
            return None
        project.name = name
        self.projects.update(project)
        return project

    def delete_project(self, project_id: str) -> None:
        self.projects.delete(project_id)
        project_dir = self.storage_dir / project_id
        if project_dir.exists():
            shutil.rmtree(project_dir, ignore_errors=True)

    def set_active_dataset(self, project_id: str, dataset_id: str) -> Project | None:
        project = self.projects.get(project_id)
        if not project:
            return None
        project.active_dataset_id = dataset_id
        self.projects.update(project)
        return project

    def project_dir(self, project_id: str) -> Path:
        return self.storage_dir / project_id

    def save_analysis_record(
        self,
        project_id: str,
        user_query: str,
        resolved_query: str,
        task_type: str,
        status: str,
        dataset_id: str | None = None,
        goal: str = "",
        main_findings: list[str] | None = None,
        limitations: list[str] | None = None,
    ) -> AnalysisRecord:
        now = datetime.now(timezone.utc).isoformat()
        record = AnalysisRecord(
            analysis_id=f"ana_{uuid.uuid4().hex[:10]}",
            project_id=project_id,
            dataset_id=dataset_id,
            user_query=user_query,
            resolved_query=resolved_query,
            task_type=task_type,
            status=status,
            goal=goal,
            main_findings=main_findings or [],
            limitations=limitations or [],
            created_at=now,
            updated_at=now,
        )
        self.analyses.create(record)
        analysis_path = self.project_dir(project_id) / "analyses" / f"{record.analysis_id}.json"
        analysis_path.write_text(json.dumps(record.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return record

    def list_analyses(self, project_id: str) -> list[AnalysisRecord]:
        return self.analyses.list_by_project(project_id)

    @staticmethod
    def file_hash(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(8192), b""):
                digest.update(chunk)
        return f"sha256:{digest.hexdigest()}"
