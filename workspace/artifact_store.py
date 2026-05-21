from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from persistence.repositories import ArtifactRepository
from workspace.workspace_types import ArtifactRecord


class ArtifactStore:
    def __init__(self, repo: ArtifactRepository, storage_dir: Path) -> None:
        self.repo = repo
        self.storage_dir = storage_dir

    def save_markdown_report(
        self,
        project_id: str,
        content: str,
        name: str,
        analysis_id: str | None = None,
        metadata: dict | None = None,
    ) -> ArtifactRecord:
        reports_dir = self.storage_dir / project_id / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        path = reports_dir / name
        path.write_text(content, encoding="utf-8")
        record = ArtifactRecord(
            artifact_id=f"art_{uuid.uuid4().hex[:10]}",
            project_id=project_id,
            analysis_id=analysis_id,
            artifact_type="markdown_report",
            name=name,
            path=str(path),
            content={"preview": content[:500]},
            metadata=metadata or {},
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self.repo.create(record)
        return record

    def save_sql_artifact(
        self,
        project_id: str,
        sql: str,
        name: str,
        analysis_id: str | None = None,
        metadata: dict | None = None,
    ) -> ArtifactRecord:
        artifacts_dir = self.storage_dir / project_id / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        path = artifacts_dir / name
        path.write_text(sql, encoding="utf-8")
        record = ArtifactRecord(
            artifact_id=f"art_{uuid.uuid4().hex[:10]}",
            project_id=project_id,
            analysis_id=analysis_id,
            artifact_type="sql",
            name=name,
            path=str(path),
            content={"sql": sql},
            metadata=metadata or {},
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self.repo.create(record)
        return record

    def save_chart_spec(
        self,
        project_id: str,
        chart_spec: dict,
        name: str,
        analysis_id: str | None = None,
    ) -> ArtifactRecord:
        import json

        artifacts_dir = self.storage_dir / project_id / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        path = artifacts_dir / name
        path.write_text(json.dumps(chart_spec, ensure_ascii=False, indent=2), encoding="utf-8")
        record = ArtifactRecord(
            artifact_id=f"art_{uuid.uuid4().hex[:10]}",
            project_id=project_id,
            analysis_id=analysis_id,
            artifact_type="chart_spec",
            name=name,
            path=str(path),
            content=chart_spec,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self.repo.create(record)
        return record

    def list_artifacts(self, project_id: str) -> list[ArtifactRecord]:
        return self.repo.list_by_project(project_id)

    def delete_artifact(self, artifact_id: str) -> None:
        pass
