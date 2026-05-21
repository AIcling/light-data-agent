from __future__ import annotations

import hashlib
import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from persistence.sqlite_store import SQLiteStore
from workspace.workspace_types import AnalysisRecord, ArtifactRecord, DatasetRecord, MemoryItem, Project


class ProjectRepository:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def create(self, name: str, description: str = "", metadata: dict | None = None) -> Project:
        project_id = f"proj_{uuid.uuid4().hex[:10]}"
        now = datetime.now(timezone.utc).isoformat()
        project = Project(
            project_id=project_id,
            name=name,
            description=description,
            metadata=metadata or {},
            created_at=now,
            updated_at=now,
        )
        with self.store.connect() as conn:
            conn.execute(
                """
                INSERT INTO projects (project_id, name, description, active_dataset_id, metadata_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project.project_id,
                    project.name,
                    project.description,
                    project.active_dataset_id,
                    self.store.dumps(project.metadata),
                    project.created_at,
                    project.updated_at,
                ),
            )
        return project

    def list_projects(self) -> list[Project]:
        with self.store.connect() as conn:
            rows = conn.execute("SELECT * FROM projects ORDER BY updated_at DESC").fetchall()
        return [self._row_to_project(row) for row in rows]

    def get(self, project_id: str) -> Project | None:
        with self.store.connect() as conn:
            row = conn.execute("SELECT * FROM projects WHERE project_id = ?", (project_id,)).fetchone()
        return self._row_to_project(row) if row else None

    def update(self, project: Project) -> None:
        project.updated_at = datetime.now(timezone.utc).isoformat()
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE projects SET name=?, description=?, active_dataset_id=?, metadata_json=?, updated_at=?
                WHERE project_id=?
                """,
                (
                    project.name,
                    project.description,
                    project.active_dataset_id,
                    self.store.dumps(project.metadata),
                    project.updated_at,
                    project.project_id,
                ),
            )

    def delete(self, project_id: str) -> None:
        with self.store.connect() as conn:
            conn.execute("DELETE FROM projects WHERE project_id = ?", (project_id,))
            conn.execute("DELETE FROM datasets WHERE project_id = ?", (project_id,))
            conn.execute("DELETE FROM memory_items WHERE project_id = ?", (project_id,))
            conn.execute("DELETE FROM analyses WHERE project_id = ?", (project_id,))
            conn.execute("DELETE FROM artifacts WHERE project_id = ?", (project_id,))
            conn.execute("DELETE FROM queries WHERE project_id = ?", (project_id,))

    def _row_to_project(self, row) -> Project:
        return Project(
            project_id=row["project_id"],
            name=row["name"],
            description=row["description"] or "",
            active_dataset_id=row["active_dataset_id"],
            metadata=self.store.loads(row["metadata_json"], {}),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


class DatasetRepository:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def create(self, record: DatasetRecord) -> DatasetRecord:
        with self.store.connect() as conn:
            conn.execute(
                """
                INSERT INTO datasets (
                    dataset_id, project_id, name, source_type, file_path, file_hash,
                    table_name, row_count, column_count, schema_version, schema_json,
                    created_at, last_used_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.dataset_id,
                    record.project_id,
                    record.name,
                    record.source_type,
                    record.file_path,
                    record.file_hash,
                    record.table_name,
                    record.row_count,
                    record.column_count,
                    record.schema_version,
                    self.store.dumps(record.schema_json),
                    record.created_at,
                    record.last_used_at,
                ),
            )
        return record

    def list_by_project(self, project_id: str) -> list[DatasetRecord]:
        with self.store.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM datasets WHERE project_id = ? ORDER BY last_used_at DESC",
                (project_id,),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def get(self, dataset_id: str) -> DatasetRecord | None:
        with self.store.connect() as conn:
            row = conn.execute("SELECT * FROM datasets WHERE dataset_id = ?", (dataset_id,)).fetchone()
        return self._row_to_record(row) if row else None

    def update(self, record: DatasetRecord) -> None:
        record.last_used_at = datetime.now(timezone.utc).isoformat()
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE datasets SET name=?, file_path=?, file_hash=?, table_name=?,
                row_count=?, column_count=?, schema_version=?, schema_json=?, last_used_at=?
                WHERE dataset_id=?
                """,
                (
                    record.name,
                    record.file_path,
                    record.file_hash,
                    record.table_name,
                    record.row_count,
                    record.column_count,
                    record.schema_version,
                    self.store.dumps(record.schema_json),
                    record.last_used_at,
                    record.dataset_id,
                ),
            )

    def delete(self, dataset_id: str) -> None:
        with self.store.connect() as conn:
            conn.execute("DELETE FROM datasets WHERE dataset_id = ?", (dataset_id,))

    def _row_to_record(self, row) -> DatasetRecord:
        return DatasetRecord(
            dataset_id=row["dataset_id"],
            project_id=row["project_id"],
            name=row["name"],
            source_type=row["source_type"],
            file_path=row["file_path"] or "",
            file_hash=row["file_hash"] or "",
            table_name=row["table_name"],
            row_count=row["row_count"],
            column_count=row["column_count"],
            schema_version=row["schema_version"],
            schema_json=self.store.loads(row["schema_json"], {}),
            created_at=row["created_at"],
            last_used_at=row["last_used_at"],
        )


class MemoryRepository:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def put(self, item: MemoryItem) -> MemoryItem:
        item.updated_at = datetime.now(timezone.utc).isoformat()
        with self.store.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO memory_items (
                    memory_id, project_id, dataset_id, scope, memory_type, key, value,
                    confidence, source, metadata_json, created_at, updated_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.memory_id,
                    item.project_id,
                    item.dataset_id,
                    item.scope,
                    item.memory_type,
                    item.key,
                    item.value,
                    item.confidence,
                    item.source,
                    self.store.dumps(item.metadata),
                    item.created_at,
                    item.updated_at,
                    item.expires_at,
                ),
            )
        return item

    def get(self, project_id: str, scope: str, memory_type: str, key: str) -> MemoryItem | None:
        with self.store.connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM memory_items
                WHERE project_id=? AND scope=? AND memory_type=? AND key=?
                ORDER BY updated_at DESC LIMIT 1
                """,
                (project_id, scope, memory_type, key),
            ).fetchone()
        return self._row_to_item(row) if row else None

    def search(
        self,
        project_id: str,
        dataset_id: str | None = None,
        scope: str | None = None,
        memory_type: str | None = None,
    ) -> list[MemoryItem]:
        query = "SELECT * FROM memory_items WHERE project_id = ?"
        params: list[Any] = [project_id]
        if dataset_id:
            query += " AND (dataset_id = ? OR dataset_id IS NULL)"
            params.append(dataset_id)
        if scope:
            query += " AND scope = ?"
            params.append(scope)
        if memory_type:
            query += " AND memory_type = ?"
            params.append(memory_type)
        query += " ORDER BY updated_at DESC"
        with self.store.connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_item(row) for row in rows]

    def delete(self, memory_id: str) -> None:
        with self.store.connect() as conn:
            conn.execute("DELETE FROM memory_items WHERE memory_id = ?", (memory_id,))

    def clear_scope(self, project_id: str, scope: str, dataset_id: str | None = None) -> None:
        query = "DELETE FROM memory_items WHERE project_id = ? AND scope = ?"
        params: list[Any] = [project_id, scope]
        if dataset_id:
            query += " AND dataset_id = ?"
            params.append(dataset_id)
        with self.store.connect() as conn:
            conn.execute(query, params)

    def _row_to_item(self, row) -> MemoryItem:
        return MemoryItem(
            memory_id=row["memory_id"],
            project_id=row["project_id"],
            dataset_id=row["dataset_id"],
            scope=row["scope"],
            memory_type=row["memory_type"],
            key=row["key"],
            value=row["value"],
            confidence=row["confidence"],
            source=row["source"],
            metadata=self.store.loads(row["metadata_json"], {}),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            expires_at=row["expires_at"],
        )


class AnalysisRepository:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def create(self, record: AnalysisRecord) -> AnalysisRecord:
        with self.store.connect() as conn:
            conn.execute(
                """
                INSERT INTO analyses (
                    analysis_id, project_id, dataset_id, user_query, resolved_query,
                    task_type, status, goal, main_findings_json, limitations_json,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.analysis_id,
                    record.project_id,
                    record.dataset_id,
                    record.user_query,
                    record.resolved_query,
                    record.task_type,
                    record.status,
                    record.goal,
                    self.store.dumps(record.main_findings),
                    self.store.dumps(record.limitations),
                    record.created_at,
                    record.updated_at,
                ),
            )
        return record

    def update(self, record: AnalysisRecord) -> None:
        record.updated_at = datetime.now(timezone.utc).isoformat()
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE analyses SET status=?, goal=?, main_findings_json=?, limitations_json=?, updated_at=?
                WHERE analysis_id=?
                """,
                (
                    record.status,
                    record.goal,
                    self.store.dumps(record.main_findings),
                    self.store.dumps(record.limitations),
                    record.updated_at,
                    record.analysis_id,
                ),
            )

    def list_by_project(self, project_id: str, limit: int = 50) -> list[AnalysisRecord]:
        with self.store.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM analyses WHERE project_id = ? ORDER BY created_at DESC LIMIT ?",
                (project_id, limit),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def get(self, analysis_id: str) -> AnalysisRecord | None:
        with self.store.connect() as conn:
            row = conn.execute("SELECT * FROM analyses WHERE analysis_id = ?", (analysis_id,)).fetchone()
        return self._row_to_record(row) if row else None

    def _row_to_record(self, row) -> AnalysisRecord:
        return AnalysisRecord(
            analysis_id=row["analysis_id"],
            project_id=row["project_id"],
            dataset_id=row["dataset_id"],
            user_query=row["user_query"],
            resolved_query=row["resolved_query"] or "",
            task_type=row["task_type"] or "",
            status=row["status"],
            goal=row["goal"] or "",
            main_findings=self.store.loads(row["main_findings_json"], []),
            limitations=self.store.loads(row["limitations_json"], []),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


class ArtifactRepository:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def create(self, record: ArtifactRecord) -> ArtifactRecord:
        with self.store.connect() as conn:
            conn.execute(
                """
                INSERT INTO artifacts (
                    artifact_id, project_id, analysis_id, artifact_type, name,
                    path, content_json, metadata_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.artifact_id,
                    record.project_id,
                    record.analysis_id,
                    record.artifact_type,
                    record.name,
                    record.path,
                    self.store.dumps(record.content),
                    self.store.dumps(record.metadata),
                    record.created_at,
                ),
            )
        return record

    def list_by_project(self, project_id: str, limit: int = 50) -> list[ArtifactRecord]:
        with self.store.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM artifacts WHERE project_id = ? ORDER BY created_at DESC LIMIT ?",
                (project_id, limit),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def _row_to_record(self, row) -> ArtifactRecord:
        return ArtifactRecord(
            artifact_id=row["artifact_id"],
            project_id=row["project_id"],
            analysis_id=row["analysis_id"],
            artifact_type=row["artifact_type"],
            name=row["name"],
            path=row["path"] or "",
            content=self.store.loads(row["content_json"], {}),
            metadata=self.store.loads(row["metadata_json"], {}),
            created_at=row["created_at"],
        )
