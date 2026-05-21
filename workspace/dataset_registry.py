from __future__ import annotations

import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from core.types import TableSchema
from persistence.repositories import DatasetRepository
from workspace.workspace_types import DatasetRecord


class DatasetRegistry:
    def __init__(self, repo: DatasetRepository, storage_dir: Path) -> None:
        self.repo = repo
        self.storage_dir = storage_dir

    def register_csv(
        self,
        project_id: str,
        source_path: Path,
        table_name: str,
        schema: TableSchema,
        name: str | None = None,
    ) -> DatasetRecord:
        dataset_id = f"ds_{uuid.uuid4().hex[:10]}"
        project_datasets = self.storage_dir / project_id / "datasets"
        project_datasets.mkdir(parents=True, exist_ok=True)
        dest = project_datasets / f"{dataset_id}_{source_path.name}"
        shutil.copy2(source_path, dest)

        from workspace.workspace_types import AnalysisRecord, ArtifactRecord, DatasetRecord, MemoryItem, Project

        now = datetime.now(timezone.utc).isoformat()
        record = DatasetRecord(
            dataset_id=dataset_id,
            project_id=project_id,
            name=name or source_path.stem,
            source_type="csv",
            file_path=str(dest),
            file_hash=ProjectManager.file_hash(dest),
            table_name=table_name,
            row_count=schema.row_count,
            column_count=len(schema.columns),
            schema_version=1,
            schema_json=schema.to_dict(),
            created_at=now,
            last_used_at=now,
        )
        self.repo.create(record)
        schema_path = self.storage_dir / project_id / "schemas" / f"{dataset_id}_schema.json"
        schema_path.parent.mkdir(parents=True, exist_ok=True)
        schema_path.write_text(
            __import__("json").dumps(schema.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return record

    def register_uploaded_bytes(
        self,
        project_id: str,
        filename: str,
        content: bytes,
        table_name: str,
        schema: TableSchema,
    ) -> DatasetRecord:
        project_datasets = self.storage_dir / project_id / "datasets"
        project_datasets.mkdir(parents=True, exist_ok=True)
        dataset_id = f"ds_{uuid.uuid4().hex[:10]}"
        dest = project_datasets / f"{dataset_id}_{filename}"
        dest.write_bytes(content)
        return self.register_csv(project_id, dest, table_name, schema, name=Path(filename).stem)

    def list_datasets(self, project_id: str) -> list[DatasetRecord]:
        return self.repo.list_by_project(project_id)

    def get_dataset(self, dataset_id: str) -> DatasetRecord | None:
        return self.repo.get(dataset_id)

    def delete_dataset(self, dataset_id: str) -> None:
        record = self.repo.get(dataset_id)
        if record and record.file_path:
            path = Path(record.file_path)
            if path.exists():
                path.unlink()
        self.repo.delete(dataset_id)

    def load_dataframe(self, record: DatasetRecord) -> pd.DataFrame:
        return pd.read_csv(record.file_path)

    def update_schema(self, record: DatasetRecord, schema: TableSchema) -> DatasetRecord:
        record.schema_json = schema.to_dict()
        record.row_count = schema.row_count
        record.column_count = len(schema.columns)
        record.schema_version += 1
        self.repo.update(record)
        return record
