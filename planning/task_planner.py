from __future__ import annotations

from dataclasses import dataclass

from core.types import AnalysisPlan, IntentResult, TableSchema
from planning.analysis_plan import AnalysisPlanBuilder
from planning.intent_parser import RuleBasedIntentParser
from schema_grounding.cannot_answer import CannotAnswerDetector
from memory.memory_store import MemoryStore


@dataclass
class TaskPlanner:
    intent_parser: RuleBasedIntentParser | None = None
    plan_builder: AnalysisPlanBuilder | None = None
    cannot_answer_detector: CannotAnswerDetector | None = None

    def __post_init__(self) -> None:
        self.intent_parser = self.intent_parser or RuleBasedIntentParser()
        self.plan_builder = self.plan_builder or AnalysisPlanBuilder()
        self.cannot_answer_detector = self.cannot_answer_detector or CannotAnswerDetector()

    def plan(
        self,
        question: str,
        schema: TableSchema,
        memory: MemoryStore | None = None,
        derived_from_memory: bool = False,
    ) -> tuple[IntentResult, AnalysisPlan, dict | None]:
        intent = self.intent_parser.parse(question, schema, memory)
        cannot = self.cannot_answer_detector.detect(question, schema, intent.task_type)
        if cannot and intent.task_type not in {"contribution_analysis", "data_quality", "report_generation"}:
            return intent, AnalysisPlan(task_type=intent.task_type, goal=question), cannot
        analysis_plan = self.plan_builder.build(question, schema, intent, derived_from_memory)
        return intent, analysis_plan, None
