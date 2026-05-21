from __future__ import annotations


def quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def strip_trailing_semicolon(sql: str) -> str:
    return sql.strip().rstrip(";").strip()
