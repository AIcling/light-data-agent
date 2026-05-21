from __future__ import annotations

from core.agent import DataAgent
from core.config import AppConfig
from memory.session_memory import SessionMemory


def build_agent(query_engine):
    config = AppConfig(max_result_rows=100, max_sql_repair_attempts=1)
    return DataAgent(
        config=config,
        query_engine=query_engine,
        memory=SessionMemory(),
    )


def test_agent_answers_required_end_to_end_questions(sample_schema, query_engine):
    agent = build_agent(query_engine)
    questions = [
        "每个月销售额是多少？",
        "哪个地区销售额最高？",
        "不同产品类别的平均利润是多少？",
        "销售额最高的前 5 个产品类别是什么？",
        "数据里有没有缺失值？",
    ]

    for question in questions:
        response = agent.answer(question, sample_schema)
        assert response.status == "success", response.to_dict()
        assert response.sql.lower().startswith("select")
        assert response.validation is not None and response.validation.valid
        assert response.result is not None
        assert response.explanation
        assert response.analysis_plan is not None


def test_agent_uses_memory_for_follow_up(sample_schema, query_engine):
    agent = build_agent(query_engine)
    first = agent.answer("各地区销售额是多少？", sample_schema)
    second = agent.answer("那利润呢？", sample_schema)
    assert first.status == "success"
    assert second.status == "success"
    assert "profit" in second.sql
    assert "region" in second.sql
