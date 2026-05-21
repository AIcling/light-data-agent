from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class AnalysisMemory:
    analysis_id: str = ""
    goal: str = ""
    steps: list[dict[str, Any]] = field(default_factory=list)
    main_findings: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    follow_up_suggestions: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def create(cls, goal: str) -> "AnalysisMemory":
        now = datetime.now(timezone.utc).isoformat()
        return cls(
            analysis_id=f"a_{uuid.uuid4().hex[:8]}",
            goal=goal,
            created_at=now,
            updated_at=now,
        )

    def add_step(
        self,
        question: str,
        sql: str,
        summary: dict[str, Any],
        explanation: str,
        insights: list[str] | None = None,
    ) -> None:
        step_id = f"s{len(self.steps) + 1}"
        self.steps.append(
            {
                "step_id": step_id,
                "question": question,
                "sql": sql,
                "summary": summary,
                "explanation": explanation,
                "insights": insights or [],
            }
        )
        if insights:
            self.main_findings.extend(insights[:2])
        self.main_findings = list(dict.fromkeys(self.main_findings))[:10]
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "analysis_id": self.analysis_id,
            "goal": self.goal,
            "steps": self.steps,
            "main_findings": self.main_findings,
            "limitations": self.limitations,
            "follow_up_suggestions": self.follow_up_suggestions,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
