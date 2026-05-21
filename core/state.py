from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from core.types import (
    AnalysisPlan,
    IntentResult,
    SQLCandidate,
    TableSchema,
    ValidationResult,
)


def new_run_id() -> str:
    return f"run_{uuid.uuid4().hex[:12]}"


def new_session_id() -> str:
    return f"session_{uuid.uuid4().hex[:8]}"


@dataclass
class TraceEvent:
    step: str
    status: str
    input_summary: dict[str, Any] = field(default_factory=dict)
    output_summary: dict[str, Any] = field(default_factory=dict)
    error: dict[str, Any] | None = None
    duration_ms: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "status": self.status,
            "input_summary": self.input_summary,
            "output_summary": self.output_summary,
            "error": self.error,
            "duration_ms": self.duration_ms,
        }


@dataclass
class AgentState:
    run_id: str
    session_id: str
    user_query: str

    normalized_query: str | None = None
    resolved_query: str | None = None
    resolution_type: str | None = None

    dataset_id: str | None = None
    table_names: list[str] = field(default_factory=list)
    schema: TableSchema | None = None
    schema_context: dict[str, Any] | None = None
    relevant_fields: dict[str, Any] | None = None
    cannot_answer: dict[str, Any] | None = None

    intent: IntentResult | None = None
    analysis_plan: AnalysisPlan | None = None

    sql_candidate: SQLCandidate | None = None
    sql_validation: ValidationResult | None = None
    repaired_sql_candidate: dict[str, Any] | None = None
    final_sql: str = ""

    execution_result: Any = None
    result_df: pd.DataFrame | None = None
    result_summary: dict[str, Any] | None = None

    explanation: str = ""
    explanation_structured: dict[str, Any] | None = None
    chart_spec: dict[str, Any] | None = None
    follow_up_suggestions: list[str] = field(default_factory=list)
    insights: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)

    memory_snapshot: dict[str, Any] | None = None
    errors: list[dict[str, Any]] = field(default_factory=list)
    trace: list[TraceEvent] = field(default_factory=list)

    status: str = "RECEIVED"
    repair_attempts: int = 0

    def add_trace(
        self,
        step: str,
        status: str,
        input_summary: dict[str, Any] | None = None,
        output_summary: dict[str, Any] | None = None,
        error: dict[str, Any] | None = None,
        duration_ms: int | None = None,
    ) -> None:
        self.trace.append(
            TraceEvent(
                step=step,
                status=status,
                input_summary=input_summary or {},
                output_summary=output_summary or {},
                error=error,
                duration_ms=duration_ms,
            )
        )
        self.status = step if status == "success" else self.status

    def add_error(self, stage: str, message: str, details: dict[str, Any] | None = None) -> None:
        self.errors.append({"stage": stage, "message": message, "details": details or {}})

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "session_id": self.session_id,
            "user_query": self.user_query,
            "normalized_query": self.normalized_query,
            "resolved_query": self.resolved_query,
            "resolution_type": self.resolution_type,
            "dataset_id": self.dataset_id,
            "table_names": self.table_names,
            "schema_context": self.schema_context,
            "relevant_fields": self.relevant_fields,
            "cannot_answer": self.cannot_answer,
            "intent": self.intent.to_dict() if self.intent else None,
            "analysis_plan": self.analysis_plan.to_dict() if self.analysis_plan else None,
            "sql_candidate": self.sql_candidate.to_dict() if self.sql_candidate else None,
            "sql_validation": self.sql_validation.to_dict() if self.sql_validation else None,
            "repaired_sql_candidate": self.repaired_sql_candidate,
            "final_sql": self.final_sql,
            "result_summary": self.result_summary,
            "explanation": self.explanation,
            "explanation_structured": self.explanation_structured,
            "chart_spec": self.chart_spec,
            "follow_up_suggestions": self.follow_up_suggestions,
            "insights": self.insights,
            "limitations": self.limitations,
            "memory_snapshot": self.memory_snapshot,
            "errors": self.errors,
            "trace": [event.to_dict() for event in self.trace],
            "status": self.status,
            "repair_attempts": self.repair_attempts,
        }
