from __future__ import annotations

import streamlit as st

from workspace.project_manager import ProjectManager


def render_artifact_panel(workspace: ProjectManager, project_id: str) -> None:
    st.subheader("Artifacts & Reports")
    artifacts = workspace.artifact_store.list_artifacts(project_id)
    if not artifacts:
        st.caption("No artifacts yet. Run an analysis or generate a report.")
        return
    for art in artifacts[:20]:
        st.write(f"- **{art.artifact_type}**: {art.name} ({art.created_at[:19]})")
        if art.path and art.artifact_type == "markdown_report":
            try:
                from pathlib import Path
                content = Path(art.path).read_text(encoding="utf-8")
                with st.expander(art.name):
                    st.markdown(content[:2000])
            except Exception:
                pass
