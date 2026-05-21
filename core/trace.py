from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.state import AgentState


class TraceLogger:
    def __init__(self, log_dir: str | Path = "logs") -> None:
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / "agent_runs.jsonl"

    def log_run(self, state: AgentState) -> None:
        record = {
            "run_id": state.run_id,
            "session_id": state.session_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_query": state.user_query,
            "resolved_query": state.resolved_query,
            "task_type": state.intent.task_type if state.intent else None,
            "sql": state.final_sql,
            "validation_passed": (
                state.sql_validation.valid if state.sql_validation else False
            ),
            "repair_attempted": state.repair_attempts > 0,
            "execution_time_ms": self._execution_time(state),
            "row_count": (
                state.result_summary.get("row_count") if state.result_summary else 0
            ),
            "status": "success" if not state.errors else "error",
            "trace": [event.to_dict() for event in state.trace],
        }
        with self.log_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

    def _execution_time(self, state: AgentState) -> int | None:
        for event in reversed(state.trace):
            if event.step == "EXECUTED" and event.duration_ms is not None:
                return event.duration_ms
        return None


def workflow_status_labels(state: AgentState) -> list[dict[str, Any]]:
    steps = [
        ("CONTEXT_RESOLVED", "Context resolved"),
        ("SCHEMA_GROUNDED", "Schema grounded"),
        ("INTENT_PARSED", "Intent parsed"),
        ("PLAN_CREATED", "Plan created"),
        ("SQL_GENERATED", "SQL generated"),
        ("SQL_VALIDATED", "SQL validated"),
        ("EXECUTED", "Query executed"),
        ("EXPLAINED", "Result explained"),
        ("MEMORY_UPDATED", "Memory updated"),
    ]
    completed = {event.step for event in state.trace if event.status == "success"}
    failed = {event.step for event in state.trace if event.status == "failed"}
    labels: list[dict[str, Any]] = []
    for step_id, label in steps:
        if step_id in failed:
            status = "failed"
        elif step_id in completed:
            status = "success"
        elif state.status == step_id:
            status = "running"
        else:
            status = "pending"
        labels.append({"step": step_id, "label": label, "status": status})
    if state.cannot_answer:
        labels.append(
            {
                "step": "CANNOT_ANSWER",
                "label": "Cannot answer with current schema",
                "status": "warning",
            }
        )
    if state.repair_attempts > 0:
        labels.append(
            {
                "step": "SQL_REPAIR_ATTEMPTED",
                "label": f"Repair attempted ({state.repair_attempts}x)",
                "status": "success" if state.final_sql else "failed",
            }
        )
    return labels
