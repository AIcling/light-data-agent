from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from core.config import AppConfig


class LLMClientError(RuntimeError):
    pass


@dataclass
class LLMClient:
    config: AppConfig

    @property
    def is_available(self) -> bool:
        return (
            self.config.llm_provider == "openai"
            and self.config.has_llm_credentials
        )

    def generate_json(self, prompt: str) -> dict[str, Any]:
        if not self.is_available:
            raise LLMClientError("LLM API key is not configured.")
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - dependency is declared.
            raise LLMClientError("openai package is not installed.") from exc

        client_kwargs: dict[str, Any] = {
            "api_key": self.config.api_key,
            "timeout": self.config.llm_timeout,
        }
        if self.config.llm_base_url:
            client_kwargs["base_url"] = self.config.llm_base_url

        client = OpenAI(**client_kwargs)
        response = client.chat.completions.create(
            model=self.config.llm_model,
            messages=[
                {
                    "role": "system",
                    "content": "Return valid JSON only.",
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        content = response.choices[0].message.content or "{}"
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMClientError(f"LLM returned invalid JSON: {content}") from exc
