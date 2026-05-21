from __future__ import annotations

import re


INJECTION_PATTERNS = [
    r"ignore (?:all )?previous instructions",
    r"忽略(?:以上|之前|上面)(?:的)?指令",
    r"system prompt",
    r"你现在是",
    r"drop table",
    r"delete from",
    r";\s*drop",
    r"read\s+local\s+file",
    r"读取本地文件",
]


class PromptGuard:
    def check(self, user_input: str) -> dict:
        warnings: list[str] = []
        blocked = False
        for pattern in INJECTION_PATTERNS:
            if re.search(pattern, user_input, re.IGNORECASE):
                warnings.append(f"Potential prompt injection pattern detected: {pattern}")
                if "drop" in pattern or "delete" in pattern:
                    blocked = True
        return {"safe": not blocked, "warnings": warnings, "blocked": blocked}
