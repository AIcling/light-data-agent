from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from persistence.repositories import MemoryRepository
from workspace.workspace_types import MemoryItem


class PreferenceMemoryStore:
    DEFAULTS = {
        "preferred_language": "zh",
        "preferred_chart_style": "plotly",
        "show_sql_by_default": True,
        "show_debug_trace": False,
        "default_limit": 100,
    }

    def __init__(self, repo: MemoryRepository) -> None:
        self.repo = repo

    def load(self, project_id: str) -> dict[str, Any]:
        item = self.repo.get(project_id, "project", "user_preference", "preferences")
        if item:
            return {**self.DEFAULTS, **json.loads(item.value)}
        return dict(self.DEFAULTS)

    def save(self, project_id: str, preferences: dict[str, Any]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        merged = {**self.DEFAULTS, **preferences}
        self.repo.put(
            MemoryItem(
                memory_id=f"mem_{uuid.uuid4().hex[:10]}",
                project_id=project_id,
                scope="project",
                memory_type="user_preference",
                key="preferences",
                value=json.dumps(merged, ensure_ascii=False),
                source="user",
                created_at=now,
                updated_at=now,
            )
        )
