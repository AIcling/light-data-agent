from __future__ import annotations

import streamlit as st

from core.config import AppConfig
from memory.memory_store import MemoryStore


def render_memory_panel(memory: MemoryStore, config: AppConfig) -> None:
    st.subheader("Memory")
    data = memory.to_dict()

    tab1, tab2, tab3, tab4 = st.tabs(["Session", "Project", "Aliases", "Preferences"])
    with tab1:
        st.json(data.get("session", {}))
        if st.button("Clear session memory"):
            memory.clear_session()
            st.success("Session memory cleared.")
            st.rerun()

    with tab2:
        st.json(data.get("project_memory") or {})
        st.json(data.get("dataset") or {})

    with tab3:
        aliases = data.get("field_aliases", {})
        if aliases:
            st.json(aliases)
        else:
            st.caption("No field aliases saved.")
        if config.allow_user_memory_edit:
            alias_key = st.text_input("Alias (e.g. 销售额)")
            alias_val = st.text_input("Column name (e.g. sales_amount)")
            if st.button("Save alias") and alias_key and alias_val:
                memory.put_field_alias(alias_key, alias_val, source="user_correction")
                st.success("Alias saved.")
                st.rerun()

    with tab4:
        st.json(data.get("preferences", {}))

    st.markdown("**Recent Queries**")
    for q in data.get("queries", [])[-5:]:
        st.write(f"- {q.get('user_query')} → `{q.get('sql', '')[:80]}`")
