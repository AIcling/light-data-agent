from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class QueryMemory:
    query_id: str = ""
    user_query: str = ""
    resolved_query: str = ""
    sql: str = ""
    used_columns: list[str] = field(default_factory=list)
    result_summary: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    status: str = "success"

    @classmethod
    def create(
        cls,
        user_query: str,
        resolved_query: str,
        sql: str,
        used_columns: list[str],
        result_summary: dict[str, Any],
        status: str = "success",
    ) -> "QueryMemory":
        return cls(
            query_id=f"q_{uuid.uuid4().hex[:8]}",
            user_query=user_query,
            resolved_query=resolved_query,
            sql=sql,
            used_columns=used_columns,
            result_summary=result_summary,
            created_at=datetime.now(timezone.utc).isoformat(),
            status=status,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_id": self.query_id,
            "user_query": self.user_query,
            "resolved_query": self.resolved_query,
            "sql": self.sql,
            "used_columns": self.used_columns,
            "result_summary": self.result_summary,
            "created_at": self.created_at,
            "status": self.status,
        }
