from __future__ import annotations


class AgentError(Exception):
    """Base error for agent workflow failures."""


class CannotAnswerError(AgentError):
    def __init__(self, reason: str, alternatives: list[str] | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.alternatives = alternatives or []


class SQLValidationError(AgentError):
    pass


class SQLRepairError(AgentError):
    pass


class SchemaGroundingError(AgentError):
    pass
