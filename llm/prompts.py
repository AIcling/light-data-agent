from __future__ import annotations

from core.types import IntentResult, TableSchema


SQL_GENERATION_PROMPT = """You are a data analysis SQL generator.

Task: generate one DuckDB SELECT query from the user question and schema.

Strict rules:
1. Only generate SELECT queries.
2. Do not generate DELETE, UPDATE, INSERT, DROP, ALTER, CREATE, REPLACE, COPY, ATTACH, or PRAGMA.
3. Only use tables and columns listed in the schema.
4. Add LIMIT 100 unless the query is an aggregate that returns a tiny result.
5. Return JSON only. Do not include markdown.
6. If the question cannot be answered from the schema, set cannot_answer=true.

User question:
{question}

Intent:
{intent}

Schema:
{schema}

Return this JSON shape:
{{
  "cannot_answer": false,
  "sql": "...",
  "used_tables": ["..."],
  "used_columns": ["..."],
  "reasoning": "..."
}}
"""


def build_sql_generation_prompt(
    question: str,
    schema: TableSchema,
    intent: IntentResult,
) -> str:
    return SQL_GENERATION_PROMPT.format(
        question=question,
        intent=intent.to_dict(),
        schema=schema.to_prompt_text(),
    )
