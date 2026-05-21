from __future__ import annotations

import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dependency is declared, fallback helps imports.
    load_dotenv = None


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class AppConfig:
    llm_provider: str = "openai"
    openai_api_key: str = ""
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str = ""
    llm_timeout: int = 60
    app_env: str = "development"
    max_upload_size_mb: int = 50
    max_result_rows: int = 100
    max_sql_repair_attempts: int = 1
    query_timeout_seconds: int = 30
    enable_sql_validation: bool = True
    allow_write_sql: bool = False
    mask_sensitive_columns: bool = True
    enable_project_workspace: bool = True
    workspace_storage_dir: str = "storage/projects"
    default_project_name: str = "Default Project"
    persistence_backend: str = "sqlite"
    sqlite_db_path: str = "storage/data_agent.db"
    enable_persistent_memory: bool = True
    memory_confidence_threshold: float = 0.65
    allow_user_memory_edit: bool = True
    enable_multi_step_plan: bool = True
    max_plan_steps: int = 6
    enable_plan_revision: bool = True
    enable_result_critic: bool = True
    min_trend_points: int = 3

    @property
    def api_key(self) -> str:
        return self.openai_api_key or self.llm_api_key

    @property
    def has_llm_credentials(self) -> bool:
        return bool(self.api_key)


def load_config() -> AppConfig:
    if load_dotenv is not None:
        load_dotenv()

    return AppConfig(
        llm_provider=os.getenv("LLM_PROVIDER", "openai").strip().lower(),
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        llm_api_key=os.getenv("LLM_API_KEY", "").strip(),
        llm_model=os.getenv("LLM_MODEL", "gpt-4o-mini").strip(),
        llm_base_url=os.getenv("LLM_BASE_URL", "").strip(),
        llm_timeout=_env_int("LLM_TIMEOUT", 60),
        app_env=os.getenv("APP_ENV", "development").strip(),
        max_upload_size_mb=_env_int("MAX_UPLOAD_SIZE_MB", 50),
        max_result_rows=_env_int("MAX_RESULT_ROWS", 100),
        max_sql_repair_attempts=_env_int("MAX_SQL_REPAIR_ATTEMPTS", 1),
        query_timeout_seconds=_env_int("QUERY_TIMEOUT_SECONDS", 30),
        enable_sql_validation=_env_bool("ENABLE_SQL_VALIDATION", True),
        allow_write_sql=_env_bool("ALLOW_WRITE_SQL", False),
        mask_sensitive_columns=_env_bool("MASK_SENSITIVE_COLUMNS", True),
        enable_project_workspace=_env_bool("ENABLE_PROJECT_WORKSPACE", True),
        workspace_storage_dir=os.getenv("WORKSPACE_STORAGE_DIR", "storage/projects").strip(),
        default_project_name=os.getenv("DEFAULT_PROJECT_NAME", "Default Project").strip(),
        persistence_backend=os.getenv("PERSISTENCE_BACKEND", "sqlite").strip(),
        sqlite_db_path=os.getenv("SQLITE_DB_PATH", "storage/data_agent.db").strip(),
        enable_persistent_memory=_env_bool("ENABLE_PERSISTENT_MEMORY", True),
        memory_confidence_threshold=float(os.getenv("MEMORY_CONFIDENCE_THRESHOLD", "0.65")),
        allow_user_memory_edit=_env_bool("ALLOW_USER_MEMORY_EDIT", True),
        enable_multi_step_plan=_env_bool("ENABLE_MULTI_STEP_PLAN", True),
        max_plan_steps=_env_int("MAX_PLAN_STEPS", 6),
        enable_plan_revision=_env_bool("ENABLE_PLAN_REVISION", True),
        enable_result_critic=_env_bool("ENABLE_RESULT_CRITIC", True),
        min_trend_points=_env_int("MIN_TREND_POINTS", 3),
    )
