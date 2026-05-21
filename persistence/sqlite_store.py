from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


class SQLiteStore:
    def __init__(self, db_path: str | Path = "storage/data_agent.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    project_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    active_dataset_id TEXT,
                    metadata_json TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS datasets (
                    dataset_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    source_type TEXT DEFAULT 'csv',
                    file_path TEXT,
                    file_hash TEXT,
                    table_name TEXT NOT NULL,
                    row_count INTEGER DEFAULT 0,
                    column_count INTEGER DEFAULT 0,
                    schema_version INTEGER DEFAULT 1,
                    schema_json TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    last_used_at TEXT NOT NULL,
                    FOREIGN KEY (project_id) REFERENCES projects(project_id)
                );

                CREATE TABLE IF NOT EXISTS memory_items (
                    memory_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    dataset_id TEXT,
                    scope TEXT NOT NULL,
                    memory_type TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    confidence REAL DEFAULT 1.0,
                    source TEXT DEFAULT 'system',
                    metadata_json TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    expires_at TEXT
                );

                CREATE TABLE IF NOT EXISTS analyses (
                    analysis_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    dataset_id TEXT,
                    user_query TEXT NOT NULL,
                    resolved_query TEXT,
                    task_type TEXT,
                    status TEXT NOT NULL,
                    goal TEXT,
                    main_findings_json TEXT DEFAULT '[]',
                    limitations_json TEXT DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS analysis_steps (
                    step_id TEXT PRIMARY KEY,
                    analysis_id TEXT NOT NULL,
                    step_order INTEGER NOT NULL,
                    step_type TEXT NOT NULL,
                    goal TEXT NOT NULL,
                    depends_on_json TEXT DEFAULT '[]',
                    status TEXT NOT NULL,
                    sql TEXT,
                    result_summary_json TEXT DEFAULT '{}',
                    observations_json TEXT DEFAULT '[]',
                    warnings_json TEXT DEFAULT '[]',
                    artifacts_json TEXT DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (analysis_id) REFERENCES analyses(analysis_id)
                );

                CREATE TABLE IF NOT EXISTS artifacts (
                    artifact_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    analysis_id TEXT,
                    artifact_type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    path TEXT,
                    content_json TEXT DEFAULT '{}',
                    metadata_json TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS queries (
                    query_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    dataset_id TEXT,
                    analysis_id TEXT,
                    user_query TEXT NOT NULL,
                    resolved_query TEXT,
                    sql TEXT,
                    used_columns_json TEXT DEFAULT '[]',
                    result_summary_json TEXT DEFAULT '{}',
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_datasets_project ON datasets(project_id);
                CREATE INDEX IF NOT EXISTS idx_memory_project ON memory_items(project_id);
                CREATE INDEX IF NOT EXISTS idx_analyses_project ON analyses(project_id);
                CREATE INDEX IF NOT EXISTS idx_artifacts_project ON artifacts(project_id);
                """
            )

    @staticmethod
    def dumps(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, default=str)

    @staticmethod
    def loads(value: str | None, default: Any = None) -> Any:
        if not value:
            return default if default is not None else {}
        return json.loads(value)
