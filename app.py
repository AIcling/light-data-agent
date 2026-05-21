from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from core.agent import DataAgent
from core.config import load_config
from data_layer.loader import CSVLoader, normalize_identifier
from memory.memory_store import MemoryStore
from observation.data_quality import DataQualityAnalyzer
from reporting.markdown_report import ReportBuilder
from schema_grounding.schema_extractor import EnhancedSchemaExtractor
from sql_layer.executor import QueryEngine
from sql_layer.validator import SQLValidator
from ui.artifact_panel import render_artifact_panel
from ui.memory_panel import render_memory_panel
from ui.plan_panel import render_plan_panel
from ui.workspace_panel import render_analysis_history, render_workspace_sidebar
from visualization.plot_renderer import PlotRenderer
from workspace.project_manager import ProjectManager


st.set_page_config(page_title="Light Data Agent v0.3", layout="wide")


def _json(data) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)


def _init_state(config) -> ProjectManager:
    if "memory" not in st.session_state:
        st.session_state.memory = MemoryStore()
    if "config" not in st.session_state:
        st.session_state.config = config
    if "last_response" not in st.session_state:
        st.session_state.last_response = None
    if "workspace" not in st.session_state:
        st.session_state.workspace = ProjectManager(
            storage_dir=config.workspace_storage_dir,
            db_path=config.sqlite_db_path,
        )
    if "current_project_id" not in st.session_state:
        default = st.session_state.workspace.ensure_default_project(config.default_project_name)
        st.session_state.current_project_id = default.project_id
    return st.session_state.workspace


def _ensure_project_dataset(workspace: ProjectManager, project_id: str, df, table_name: str, schema, source_path: Path | None, uploaded_bytes: tuple[str, bytes] | None):
    datasets = workspace.dataset_registry.list_datasets(project_id)
    if datasets:
        record = next((d for d in datasets if d.table_name == table_name), datasets[0])
        workspace.set_active_dataset(project_id, record.dataset_id)
        if source_path and Path(record.file_path).exists():
            df = workspace.dataset_registry.load_dataframe(record)
            schema = EnhancedSchemaExtractor().extract(df, record.table_name, dataset_id=record.dataset_id)
        return df, schema, record

    if uploaded_bytes:
        filename, content = uploaded_bytes
        record = workspace.dataset_registry.register_uploaded_bytes(
            project_id, filename, content, table_name, schema
        )
    elif source_path:
        record = workspace.dataset_registry.register_csv(project_id, source_path, table_name, schema)
    else:
        return df, schema, None

    workspace.set_active_dataset(project_id, record.dataset_id)
    schema.dataset_id = record.dataset_id
    return df, schema, record


def _build_agent(engine: QueryEngine, workspace: ProjectManager, project_id: str) -> DataAgent:
    config = st.session_state.config
    memory: MemoryStore = st.session_state.memory
    if config.enable_persistent_memory:
        memory.attach_workspace(workspace, project_id)
    agent = DataAgent(config=config, query_engine=engine, memory=memory, workspace=workspace)
    agent.set_project(project_id)
    return agent


def _render_workflow_status(response) -> None:
    st.markdown("#### Agent Workflow")
    if response.workflow_status:
        for item in response.workflow_status:
            icon = {"success": "✅", "failed": "❌", "warning": "⚠️", "pending": "⬜", "running": "🔄"}.get(
                item["status"], "⬜"
            )
            st.write(f"{icon} {item['label']}")


def main() -> None:
    config = load_config()
    workspace = _init_state(config)
    project_id = st.session_state.current_project_id if "current_project_id" in st.session_state else None

    st.title("Light Data Agent")
    project = workspace.get_project(project_id) if project_id else None
    st.caption(
        f"Project: {project.name if project else '—'} | "
        "Workspace · Persistent Memory · Multi-step Analysis"
    )

    with st.sidebar:
        if config.enable_project_workspace:
            workspace = render_workspace_sidebar(config)
            project_id = st.session_state.current_project_id
            st.session_state.memory.attach_workspace(workspace, project_id)
        else:
            workspace = st.session_state.workspace

        st.divider()
        st.header("Data Source")
        use_sample = st.checkbox("Use sample sales.csv", value=True)
        uploaded_file = st.file_uploader("Upload CSV to project", type=["csv"], disabled=use_sample)
        table_name_input = st.text_input("Table name", value="sales")

        st.divider()
        st.header("LLM")
        if config.has_llm_credentials:
            st.success(f"LLM enabled: {config.llm_model}")
        else:
            st.info("No API key — rule-based SQL active.")

        if config.enable_multi_step_plan:
            st.caption("Multi-step planning: enabled")

    loader = CSVLoader()
    schema_extractor = EnhancedSchemaExtractor()
    source_path = None
    uploaded_bytes = None

    try:
        if use_sample:
            source_path = Path("sample_data/sales.csv")
            dataset = loader.load(source_path, table_name=table_name_input or "sales")
        elif uploaded_file is not None:
            uploaded_bytes = (uploaded_file.name, uploaded_file.getvalue())
            dataset = loader.load(
                uploaded_file,
                table_name=table_name_input or Path(uploaded_file.name).stem,
                filename=uploaded_file.name,
            )
        else:
            st.info("Upload a CSV or enable sample data.")
            with st.expander("Memory & History"):
                render_memory_panel(st.session_state.memory, config)
            return

        table_name = normalize_identifier(dataset.table_name, "data")
        df = dataset.dataframe
        schema = schema_extractor.extract(
            df, table_name, dataset_id=table_name, column_mapping=dataset.column_mapping
        )

        if config.enable_project_workspace and project_id:
            df, schema, ds_record = _ensure_project_dataset(
                workspace, project_id, df, table_name, schema, source_path, uploaded_bytes
            )
            if ds_record:
                schema.dataset_id = ds_record.dataset_id
                st.session_state.active_dataset_id = ds_record.dataset_id

        st.session_state.memory.bind_dataset(schema)

    except Exception as exc:
        st.error(f"File load error: {exc}")
        return

    engine = QueryEngine(max_result_rows=config.max_result_rows)
    engine.register_dataframe(table_name, df)
    agent = _build_agent(engine, workspace, project_id)
    plot_renderer = PlotRenderer()
    quality_analyzer = DataQualityAnalyzer()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Table", table_name)
    c2.metric("Rows", f"{len(df):,}")
    c3.metric("Columns", len(df.columns))
    c4.metric("Project", project.name if project else "—")

    tabs = st.tabs(["Analyze", "Preview & Schema", "Data Quality", "History & Memory", "Artifacts"])
    with tabs[1]:
        st.dataframe(df.head(10), use_container_width=True)
        st.json(schema.to_dict())
    with tabs[2]:
        qr = quality_analyzer.analyze(df, schema.to_dict())
        st.metric("Quality Score", f"{qr['quality_score']}/100")
        for issue in qr.get("issues", []):
            st.warning(issue.get("message"))
    with tabs[3]:
        render_memory_panel(st.session_state.memory, config)
        if project_id:
            render_analysis_history(workspace, project_id)
    with tabs[4]:
        if project_id:
            render_artifact_panel(workspace, project_id)

    with tabs[0]:
        default_q = "为什么这个月销售额下降？"
        question = st.text_input("Question / Analysis Goal", value=default_q)
        run = st.button("Analyze", type="primary")

        if run and question.strip():
            response = agent.answer(question, schema, raw_df=df)
            st.session_state.last_response = response

            if response.status == "clarification":
                st.warning(response.needs_clarification.get("message", "Need clarification"))
                return

            if response.resolved_query and response.resolved_query != question:
                st.info(f"系统理解为：{response.resolved_query}")

            if response.multi_step:
                render_plan_panel(response)
            else:
                _render_workflow_status(response)

            if response.status not in {"success", "partial"}:
                if response.cannot_answer:
                    st.warning(response.cannot_answer.get("reason", ""))
                    for alt in response.cannot_answer.get("available_alternatives", []):
                        st.write(f"- {alt}")
                else:
                    st.error(f"{response.stage or 'error'}: {'; '.join(response.errors)}")
                return

            if response.analysis_plan and not response.multi_step:
                with st.expander("Analysis Plan"):
                    st.json(response.analysis_plan.to_dict())

            if response.sql:
                st.markdown("#### SQL")
                st.code(response.sql, language="sql")

            if response.result is not None and isinstance(response.result, pd.DataFrame):
                st.markdown("#### Result")
                st.dataframe(response.result, use_container_width=True)
                figure = plot_renderer.render(response.result, response.chart_spec)
                if figure is not None:
                    st.plotly_chart(figure, use_container_width=True)

            st.markdown("#### Explanation")
            st.write(response.explanation)

            if response.follow_up_suggestions:
                st.markdown("#### 后续建议")
                for s in response.follow_up_suggestions:
                    st.write(f"- {s}")

            with st.expander("Debug"):
                st.json(response.to_dict())

        st.divider()
        if st.button("Generate Report") and project_id:
            report = ReportBuilder().build(st.session_state.memory, table_name)
            art = workspace.artifact_store.save_markdown_report(
                project_id, report, f"report_{table_name}.md"
            )
            st.success(f"Report saved: {art.path}")
            st.download_button("Download", report, file_name=art.name, mime="text/markdown")


if __name__ == "__main__":
    main()
