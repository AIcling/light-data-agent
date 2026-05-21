from __future__ import annotations

import streamlit as st

from workspace.project_manager import ProjectManager


def render_workspace_sidebar(config) -> ProjectManager:
    if "workspace" not in st.session_state:
        st.session_state.workspace = ProjectManager(
            storage_dir=config.workspace_storage_dir,
            db_path=config.sqlite_db_path,
        )
    workspace: ProjectManager = st.session_state.workspace

    if "current_project_id" not in st.session_state:
        default = workspace.ensure_default_project(config.default_project_name)
        st.session_state.current_project_id = default.project_id

    st.subheader("Project Workspace")
    projects = workspace.list_projects()
    project_names = {p.project_id: p.name for p in projects}
    selected = st.selectbox(
        "Project",
        options=list(project_names.keys()),
        format_func=lambda pid: project_names.get(pid, pid),
        index=max(0, list(project_names.keys()).index(st.session_state.current_project_id))
        if st.session_state.current_project_id in project_names else 0,
    )
    if selected != st.session_state.current_project_id:
        st.session_state.current_project_id = selected
        st.session_state.memory.reset_for_project_switch()
        st.session_state.last_response = None
        st.rerun()

    project = workspace.get_project(selected)
    if project:
        st.caption(project.description or "No description")

    with st.expander("Create / Rename Project"):
        new_name = st.text_input("New project name", value="")
        if st.button("Create Project") and new_name.strip():
            created = workspace.create_project(new_name.strip())
            st.session_state.current_project_id = created.project_id
            st.session_state.memory.reset_for_project_switch()
            st.rerun()
        rename = st.text_input("Rename current project", value=project.name if project else "")
        if st.button("Rename") and project and rename.strip():
            workspace.rename_project(project.project_id, rename.strip())
            st.rerun()

    st.divider()
    st.subheader("Datasets")
    datasets = workspace.dataset_registry.list_datasets(selected)
    if datasets:
        ds_labels = {d.dataset_id: f"{d.name} ({d.row_count:,} rows)" for d in datasets}
        active_id = project.active_dataset_id if project else None
        ds_selected = st.selectbox(
            "Active dataset",
            options=list(ds_labels.keys()),
            format_func=lambda did: ds_labels.get(did, did),
            index=list(ds_labels.keys()).index(active_id) if active_id in ds_labels else 0,
        )
        if project and ds_selected != project.active_dataset_id:
            workspace.set_active_dataset(project.project_id, ds_selected)
            st.rerun()
        if st.button("Delete selected dataset"):
            workspace.dataset_registry.delete_dataset(ds_selected)
            st.rerun()
    else:
        st.caption("No datasets in this project yet.")

    return workspace


def render_analysis_history(workspace: ProjectManager, project_id: str) -> None:
    st.subheader("Analysis History")
    records = workspace.list_analyses(project_id)
    if not records:
        st.caption("No analyses yet.")
        return
    for record in records[:15]:
        with st.expander(f"{record.created_at[:19]} — {record.user_query[:60]}"):
            st.write(f"**Status:** {record.status} | **Type:** {record.task_type}")
            st.write(f"**Resolved:** {record.resolved_query}")
            if record.main_findings:
                st.markdown("**Findings:**")
                for f in record.main_findings:
                    st.write(f"- {f}")
