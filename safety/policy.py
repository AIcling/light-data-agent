from __future__ import annotations

import re

DANGEROUS_KEYWORDS = {
    "DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE", "CREATE",
    "REPLACE", "ATTACH", "COPY", "EXPORT", "INSTALL", "LOAD", "PRAGMA", "CALL",
}

SENSITIVE_PATH_PATTERNS = [
    r"/etc/",
    r"\\windows\\",
    r"c:\\users\\",
    r"\.env",
    r"\.pem",
    r"\.key",
]


def validate_policy(sql: str, allow_write_sql: bool = False) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    cleaned = sql.strip().rstrip(";")
    if ";" in cleaned:
        errors.append("Multiple SQL statements are not allowed.")
    upper = cleaned.upper()
    for keyword in DANGEROUS_KEYWORDS:
        if re.search(rf"\b{keyword}\b", upper):
            errors.append(f"Dangerous keyword '{keyword}' is not allowed.")
    if not allow_write_sql and not upper.lstrip().startswith(("SELECT", "WITH")):
        errors.append("Only read-only SELECT queries are allowed.")
    for pattern in SENSITIVE_PATH_PATTERNS:
        if re.search(pattern, sql, re.IGNORECASE):
            errors.append("Access to sensitive local paths is not allowed.")
    return errors, warnings
