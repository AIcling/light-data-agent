from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class PlanStep:
    step_id: str
    step_type: str
    goal: str
    depends_on: list[str] = field(default_factory=list)
    input_refs: list[str] = field(default_factory=list)
    output_key: str = ""
    status: str = "pending"
    sql: str = ""
    result_summary: dict[str, Any] = field(default_factory=dict)
    observations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    chart_spec: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MultiStepAnalysisPlan:
    plan_id: str
    project_id: str
    dataset_id: str
    goal: str
    plan_type: str
    status: str = "created"
    steps: list[PlanStep] = field(default_factory=list)
    final_outputs: dict[str, bool] = field(default_factory=lambda: {"summary": True, "charts": True, "report": False})
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "project_id": self.project_id,
            "dataset_id": self.dataset_id,
            "goal": self.goal,
            "plan_type": self.plan_type,
            "status": self.status,
            "steps": [s.to_dict() for s in self.steps],
            "final_outputs": self.final_outputs,
            "created_at": self.created_at,
        }
