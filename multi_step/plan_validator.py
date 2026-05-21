from __future__ import annotations

from dataclasses import dataclass

from multi_step.multi_step_plan import MultiStepAnalysisPlan


SUPPORTED_STEP_TYPES = {
    "sql_query",
    "data_quality_check",
    "contribution_decomposition",
    "chart_generation",
    "result_summary",
    "result_critic",
    "synthesis",
    "report_generation",
    "clarification",
}


@dataclass
class PlanValidator:
    def validate(self, plan: MultiStepAnalysisPlan) -> dict:
        errors: list[str] = []
        warnings: list[str] = []
        step_ids = {s.step_id for s in plan.steps}

        for step in plan.steps:
            if step.step_type not in SUPPORTED_STEP_TYPES:
                errors.append(f"Unsupported step type: {step.step_type}")
            for dep in step.depends_on:
                if dep not in step_ids:
                    errors.append(f"Step {step.step_id} depends on missing step {dep}")
            for ref in step.input_refs:
                outputs = {s.output_key for s in plan.steps if s.output_key}
                if ref and ref not in outputs:
                    warnings.append(f"Step {step.step_id} references unknown output {ref}")

        if self._has_cycle(plan):
            errors.append("Plan contains circular dependencies.")

        if len(plan.steps) > 6:
            warnings.append("Plan exceeds recommended 6 steps; may be truncated.")

        return {
            "valid": not errors,
            "errors": errors,
            "warnings": warnings,
        }

    def _has_cycle(self, plan: MultiStepAnalysisPlan) -> bool:
        graph = {s.step_id: s.depends_on for s in plan.steps}
        visited: set[str] = set()
        stack: set[str] = set()

        def visit(node: str) -> bool:
            if node in stack:
                return True
            if node in visited:
                return False
            visited.add(node)
            stack.add(node)
            for dep in graph.get(node, []):
                if visit(dep):
                    return True
            stack.remove(node)
            return False

        return any(visit(step_id) for step_id in graph)
