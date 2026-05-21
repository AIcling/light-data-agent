from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from core.types import IntentResult, TableSchema
from memory.analysis_memory import AnalysisMemory
from memory.dataset_memory import DatasetMemory
from memory.project_memory import ProjectMemory, ProjectMemoryStore
from memory.query_memory import QueryMemory
from memory.schema_memory import SchemaMemoryStore
from memory.session_memory import SessionMemory

if TYPE_CHECKING:
    from persistence.repositories import MemoryRepository
    from workspace.project_manager import ProjectManager


@dataclass
class MemoryStore:
    session: SessionMemory = field(default_factory=SessionMemory)
    dataset: DatasetMemory | None = None
    queries: list[QueryMemory] = field(default_factory=list)
    analysis: AnalysisMemory | None = None
    project_id: str = ""
    dataset_id: str = ""
    project_memory: ProjectMemory | None = None
    _workspace: "ProjectManager | None" = field(default=None, repr=False)

    def attach_workspace(self, workspace: "ProjectManager", project_id: str) -> None:
        self._workspace = workspace
        self.project_id = project_id
        self.session.project_id = project_id
        store = ProjectMemoryStore(workspace.memory_repo)
        self.project_memory = store.load(project_id)

    def bind_dataset(self, schema: TableSchema, source_type: str = "csv") -> None:
        dataset_id = schema.dataset_id or schema.table_name
        self.dataset_id = dataset_id
        if self.dataset is None or self.dataset.dataset_id != dataset_id:
            self.dataset = DatasetMemory.from_schema(schema, source_type)
            self.analysis = AnalysisMemory.create(goal=f"Analysis on {dataset_id}")
        else:
            self.dataset.schema_summary = schema.to_dict()
            self.dataset.touch()
        self.session.active_dataset_id = dataset_id
        if self._workspace and self.project_id:
            ProjectMemoryStore(self._workspace.memory_repo).update_from_schema(
                self.project_id, schema.to_dict()
            )
            self.project_memory = ProjectMemoryStore(self._workspace.memory_repo).load(self.project_id)

    def get_field_aliases(self) -> dict[str, str]:
        if not self._workspace or not self.project_id:
            return {}
        return SchemaMemoryStore(self._workspace.memory_repo).get_field_aliases(
            self.project_id, self.dataset_id or None
        )

    def put_field_alias(self, alias: str, column_name: str, source: str = "user_correction") -> None:
        if not self._workspace or not self.project_id:
            return
        SchemaMemoryStore(self._workspace.memory_repo).put_field_alias(
            self.project_id, self.dataset_id, alias, column_name, source=source
        )

    def get_preferences(self) -> dict[str, Any]:
        if not self._workspace or not self.project_id:
            from memory.preference_memory import PreferenceMemoryStore
            return PreferenceMemoryStore.DEFAULTS
        from memory.preference_memory import PreferenceMemoryStore
        return PreferenceMemoryStore(self._workspace.memory_repo).load(self.project_id)

    def record_success(
        self,
        question: str,
        resolved_query: str,
        intent: IntentResult,
        sql: str,
        result_summary: dict,
        chart_spec: dict | None = None,
        insights: list[str] | None = None,
        limitations: list[str] | None = None,
        follow_up_suggestions: list[str] | None = None,
        analysis_id: str = "",
    ) -> None:
        self.session.update(question, intent, sql, result_summary, resolved_query, chart_spec)
        if analysis_id:
            self.session.last_analysis_id = analysis_id
        query = QueryMemory.create(
            user_query=question,
            resolved_query=resolved_query,
            sql=sql,
            used_columns=intent.metric_candidates + intent.dimension_candidates + intent.time_column_candidates,
            result_summary=result_summary,
            status="success",
        )
        self.queries.append(query)
        self.queries = self.queries[-50:]
        if self.dataset:
            self.dataset.record_usage(intent.metric_candidates, intent.dimension_candidates)
        if self.analysis is None:
            self.analysis = AnalysisMemory.create(goal=resolved_query)
        self.analysis.add_step(
            question=question,
            sql=sql,
            summary=result_summary,
            explanation="",
            insights=insights,
        )
        if limitations:
            self.analysis.limitations = list(dict.fromkeys(self.analysis.limitations + limitations))[:10]
        if follow_up_suggestions:
            self.analysis.follow_up_suggestions = follow_up_suggestions
        if self._workspace and self.project_id:
            self._persist_query(query, analysis_id)
            if insights:
                store = ProjectMemoryStore(self._workspace.memory_repo)
                pm = store.load(self.project_id)
                for insight in insights[:2]:
                    store.add_finding(self.project_id, insight)

    def _persist_query(self, query: QueryMemory, analysis_id: str) -> None:
        import json
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()
        with self._workspace.store.connect() as conn:
            conn.execute(
                """
                INSERT INTO queries (
                    query_id, project_id, dataset_id, analysis_id, user_query, resolved_query,
                    sql, used_columns_json, result_summary_json, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    query.query_id,
                    self.project_id,
                    self.dataset_id or None,
                    analysis_id or None,
                    query.user_query,
                    query.resolved_query,
                    query.sql,
                    json.dumps(query.used_columns, ensure_ascii=False),
                    json.dumps(query.result_summary, ensure_ascii=False, default=str),
                    query.status,
                    now,
                ),
            )

    def record_failure(self, question: str, reason: str) -> None:
        query = QueryMemory.create(
            user_query=question,
            resolved_query=question,
            sql="",
            used_columns=[],
            result_summary={"error": reason},
            status="failed",
        )
        self.queries.append(query)
        if self._workspace and self.project_id:
            self._persist_query(query, "")

    def clear_session(self) -> None:
        self.session.clear()

    def reset_for_project_switch(self) -> None:
        self.clear_session()
        self.dataset = None
        self.analysis = AnalysisMemory.create(goal="")
        self.queries = []

    def to_dict(self) -> dict:
        return {
            "project_id": self.project_id,
            "dataset_id": self.dataset_id,
            "session": self.session.to_dict(),
            "project_memory": self.project_memory.to_dict() if self.project_memory else None,
            "dataset": self.dataset.to_dict() if self.dataset else None,
            "field_aliases": self.get_field_aliases(),
            "preferences": self.get_preferences(),
            "queries": [q.to_dict() for q in self.queries[-10:]],
            "analysis": self.analysis.to_dict() if self.analysis else None,
        }
