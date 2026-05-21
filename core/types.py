from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import pandas as pd


def _json_safe(value: Any) -> Any:
    if pd.isna(value) if not isinstance(value, (list, dict, tuple)) else False:
        return None
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


@dataclass
class ColumnMeta:
    name: str
    dtype: str
    semantic_type: str
    sample_values: list[Any]
    missing_rate: float
    unique_count: int
    min_value: Any | None = None
    max_value: Any | None = None
    mean_value: float | None = None
    role: str = ""
    quality_tags: list[str] = field(default_factory=list)
    original_name: str = ""
    aliases: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["sample_values"] = [_json_safe(v) for v in self.sample_values]
        data["min_value"] = _json_safe(self.min_value)
        data["max_value"] = _json_safe(self.max_value)
        data["mean_value"] = _json_safe(self.mean_value)
        return data


@dataclass
class TableSchema:
    table_name: str
    row_count: int
    columns: list[ColumnMeta]
    dataset_id: str = ""
    time_range: dict[str, Any] | None = None
    likely_metrics: list[str] = field(default_factory=list)
    likely_dimensions: list[str] = field(default_factory=list)
    likely_time_columns: list[str] = field(default_factory=list)

    @property
    def column_names(self) -> list[str]:
        return [column.name for column in self.columns]

    def get_column(self, name: str) -> ColumnMeta | None:
        lowered = name.lower()
        for column in self.columns:
            if column.name.lower() == lowered:
                return column
        return None

    def columns_by_semantic(self, semantic_type: str) -> list[ColumnMeta]:
        return [c for c in self.columns if c.semantic_type == semantic_type]

    def to_dict(self) -> dict[str, Any]:
        return {
            "table_name": self.table_name,
            "dataset_id": self.dataset_id,
            "row_count": self.row_count,
            "column_count": len(self.columns),
            "time_range": self.time_range,
            "likely_metrics": self.likely_metrics,
            "likely_dimensions": self.likely_dimensions,
            "likely_time_columns": self.likely_time_columns,
            "columns": [column.to_dict() for column in self.columns],
        }

    def to_prompt_text(self) -> str:
        lines = [f"table: {self.table_name}", f"row_count: {self.row_count}"]
        for column in self.columns:
            stat_bits = [
                f"name={column.name}",
                f"dtype={column.dtype}",
                f"semantic_type={column.semantic_type}",
                f"missing_rate={column.missing_rate:.3f}",
                f"unique_count={column.unique_count}",
            ]
            if column.min_value is not None:
                stat_bits.append(f"min={column.min_value}")
            if column.max_value is not None:
                stat_bits.append(f"max={column.max_value}")
            if column.mean_value is not None:
                stat_bits.append(f"mean={column.mean_value:.3f}")
            lines.append("- " + ", ".join(stat_bits))
        return "\n".join(lines)


@dataclass
class LoadedDataset:
    table_name: str
    dataframe: pd.DataFrame
    original_filename: str
    column_mapping: dict[str, str]

    @property
    def row_count(self) -> int:
        return int(len(self.dataframe))

    @property
    def column_count(self) -> int:
        return int(len(self.dataframe.columns))

    def preview(self, rows: int = 10) -> pd.DataFrame:
        return self.dataframe.head(rows)


@dataclass
class IntentResult:
    task_type: str
    metric_candidates: list[str] = field(default_factory=list)
    dimension_candidates: list[str] = field(default_factory=list)
    time_column_candidates: list[str] = field(default_factory=list)
    filters: list[dict[str, Any]] = field(default_factory=list)
    expected_output: list[str] = field(default_factory=list)
    options: dict[str, Any] = field(default_factory=dict)
    uncertain: bool = False
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AnalysisPlan:
    task_type: str
    goal: str
    data_requirements: dict[str, Any] = field(default_factory=dict)
    operations: list[dict[str, Any]] = field(default_factory=list)
    expected_output: dict[str, Any] = field(default_factory=dict)
    derived_from_memory: bool = False
    filters: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SQLCandidate:
    sql: str
    used_tables: list[str]
    used_columns: list[str]
    reasoning: str
    cannot_answer: bool = False
    error_message: str | None = None
    generated_from_plan: bool = False
    confidence: float = 0.0
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ValidationLayerResult:
    passed: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    suggestions: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    normalized_sql: str | None = None
    policy: ValidationLayerResult | None = None
    syntax: ValidationLayerResult | None = None
    schema: ValidationLayerResult | None = None
    semantic: ValidationLayerResult | None = None
    dry_run: ValidationLayerResult | None = None
    final_decision: str = "deny"

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "normalized_sql": self.normalized_sql,
            "policy": self.policy.to_dict() if self.policy else None,
            "syntax": self.syntax.to_dict() if self.syntax else None,
            "schema": self.schema.to_dict() if self.schema else None,
            "semantic": self.semantic.to_dict() if self.semantic else None,
            "dry_run": self.dry_run.to_dict() if self.dry_run else None,
            "final_decision": self.final_decision,
        }


@dataclass
class RepairResult:
    repaired: bool
    sql: str
    repair_actions: list[str] = field(default_factory=list)
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExecutionResult:
    status: str
    dataframe: pd.DataFrame
    row_count: int
    execution_time_ms: int
    columns: list[str]
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "row_count": self.row_count,
            "execution_time_ms": self.execution_time_ms,
            "columns": self.columns,
            "data": self.dataframe.head(100).to_dict(orient="records"),
            "error": self.error,
        }


@dataclass
class AgentResponse:
    status: str
    question: str
    intent: IntentResult | None = None
    sql: str = ""
    validation: ValidationResult | None = None
    result: pd.DataFrame | None = None
    result_summary: dict[str, Any] = field(default_factory=dict)
    explanation: str = ""
    chart_spec: dict[str, Any] | None = None
    stage: str | None = None
    errors: list[str] = field(default_factory=list)
    debug: dict[str, Any] = field(default_factory=dict)
    resolved_query: str = ""
    analysis_plan: AnalysisPlan | None = None
    follow_up_suggestions: list[str] = field(default_factory=list)
    cannot_answer: dict[str, Any] | None = None
    trace: list[dict[str, Any]] = field(default_factory=list)
    workflow_status: list[dict[str, Any]] = field(default_factory=list)
    run_id: str = ""
    insights: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    explanation_structured: dict[str, Any] | None = None
    multi_step_plan: dict[str, Any] | None = None
    multi_step: bool = False
    needs_clarification: dict[str, Any] | None = None
    analysis_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "question": self.question,
            "resolved_query": self.resolved_query,
            "intent": self.intent.to_dict() if self.intent else None,
            "analysis_plan": self.analysis_plan.to_dict() if self.analysis_plan else None,
            "multi_step_plan": self.multi_step_plan,
            "multi_step": self.multi_step,
            "needs_clarification": self.needs_clarification,
            "analysis_id": self.analysis_id,
            "sql": self.sql,
            "validation": self.validation.to_dict() if self.validation else None,
            "result_preview": (
                self.result.head(100).to_dict(orient="records")
                if self.result is not None
                else []
            ),
            "result_summary": self.result_summary,
            "explanation": self.explanation,
            "explanation_structured": self.explanation_structured,
            "chart": self.chart_spec,
            "follow_up_suggestions": self.follow_up_suggestions,
            "cannot_answer": self.cannot_answer,
            "insights": self.insights,
            "limitations": self.limitations,
            "stage": self.stage,
            "errors": self.errors,
            "trace": self.trace,
            "workflow_status": self.workflow_status,
            "run_id": self.run_id,
            "debug": self.debug,
        }
