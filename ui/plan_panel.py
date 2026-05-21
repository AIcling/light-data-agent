from __future__ import annotations

import streamlit as st

from core.types import AgentResponse


def render_plan_panel(response: AgentResponse) -> None:
    if not response.multi_step_plan:
        return
    st.subheader("Multi-step Analysis Plan")
    plan = response.multi_step_plan
    st.write(f"**Goal:** {plan.get('goal', '')}")
    st.write(f"**Type:** {plan.get('plan_type', '')} | **Status:** {plan.get('status', '')}")
    for step in plan.get("steps", []):
        icon = {
            "success": "✅",
            "failed": "❌",
            "skipped": "⏭️",
            "running": "🔄",
            "pending": "⬜",
        }.get(step.get("status", "pending"), "⬜")
        with st.expander(f"{icon} {step.get('step_id')}: {step.get('goal')}"):
            st.write(f"**Type:** {step.get('step_type')} | **Status:** {step.get('status')}")
            if step.get("sql"):
                st.code(step["sql"], language="sql")
            if step.get("observations"):
                st.markdown("**Observations:**")
                for obs in step["observations"]:
                    st.write(f"- {obs}")
            if step.get("warnings"):
                st.markdown("**Warnings:**")
                for warn in step["warnings"]:
                    st.warning(warn)
            if step.get("result_summary"):
                st.json(step["result_summary"])
