from __future__ import annotations

SENSITIVE_KEYWORDS = [
    "email", "phone", "mobile", "ssn", "password", "address", "身份证", "手机", "邮箱", "地址", "secret", "token",
]


class SensitiveColumnDetector:
    def detect(self, column_names: list[str]) -> list[str]:
        sensitive: list[str] = []
        for name in column_names:
            lowered = name.lower()
            if any(keyword in lowered for keyword in SENSITIVE_KEYWORDS):
                sensitive.append(name)
        return sensitive

    def should_mask(self, column_name: str, mask_enabled: bool = True) -> bool:
        if not mask_enabled:
            return False
        return column_name in self.detect([column_name])
