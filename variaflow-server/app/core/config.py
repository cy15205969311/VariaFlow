from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    return int(raw)


def _get_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    return float(raw)


def _get_env(name: str, default: str | None = None, aliases: tuple[str, ...] = ()) -> str | None:
    for key in (name, *aliases):
        value = os.getenv(key)
        if value is not None:
            return value
    return default


def _get_app_env() -> str:
    return _get_env("VARIAFLOW_APP_ENV", "development") or "development"


def _is_test_runtime() -> bool:
    app_env = _get_app_env().strip().lower()
    return (
        app_env == "test"
        or os.getenv("PYTEST_CURRENT_TEST") is not None
        or "pytest" in sys.modules
    )


def _get_primary_database_url() -> str:
    return _get_env(
        "VARIAFLOW_DATABASE_URL",
        "mysql+aiomysql://root:password@127.0.0.1:3306/variaflow",
    ) or "mysql+aiomysql://root:password@127.0.0.1:3306/variaflow"


def _get_test_database_url() -> str | None:
    return _get_env("VARIAFLOW_TEST_DATABASE_URL")


def _get_effective_database_url() -> str:
    if _is_test_runtime():
        test_database_url = _get_test_database_url()
        if not test_database_url:
            raise RuntimeError(
                "检测到测试运行环境，但未配置 VARIAFLOW_TEST_DATABASE_URL，已阻止连接主库。"
            )
        primary_database_url = _get_primary_database_url()
        if test_database_url == primary_database_url:
            raise RuntimeError(
                "VARIAFLOW_TEST_DATABASE_URL 不能与 VARIAFLOW_DATABASE_URL 相同，已阻止测试连接主库。"
            )
        return test_database_url
    return _get_primary_database_url()


@dataclass(frozen=True, slots=True)
class Settings:
    app_name: str = _get_env("VARIAFLOW_APP_NAME", "VariaFlow API") or "VariaFlow API"
    app_env: str = field(default_factory=_get_app_env)
    is_test_env: bool = field(default_factory=_is_test_runtime)
    debug: bool = _get_bool("VARIAFLOW_DEBUG", False)

    database_url: str = field(default_factory=_get_primary_database_url)
    test_database_url: str | None = field(default_factory=_get_test_database_url)
    effective_database_url: str = field(default_factory=_get_effective_database_url)
    data_root: Path = Path(os.getenv("VARIAFLOW_DATA_ROOT", "data")).resolve()
    db_pool_size: int = _get_int("VARIAFLOW_DB_POOL_SIZE", 10)
    db_max_overflow: int = _get_int("VARIAFLOW_DB_MAX_OVERFLOW", 20)
    db_pool_recycle_seconds: int = _get_int("VARIAFLOW_DB_POOL_RECYCLE_SECONDS", 1800)
    db_pool_pre_ping: bool = _get_bool("VARIAFLOW_DB_POOL_PRE_PING", True)
    default_target_variant_count: int = _get_int("VARIAFLOW_DEFAULT_TARGET_VARIANT_COUNT", 3)

    cors_allow_origins: tuple[str, ...] = tuple(
        item.strip()
        for item in os.getenv("VARIAFLOW_CORS_ALLOW_ORIGINS", "*").split(",")
        if item.strip()
    )
    scheduler_poll_interval_seconds: float = float(
        os.getenv("VARIAFLOW_SCHEDULER_POLL_INTERVAL_SECONDS", "3")
    )
    recovery_interval_seconds: float = float(
        os.getenv("VARIAFLOW_RECOVERY_INTERVAL_SECONDS", "15")
    )
    worker_lease_seconds: int = _get_int("VARIAFLOW_WORKER_LEASE_SECONDS", 120)
    worker_name: str = os.getenv("VARIAFLOW_WORKER_NAME", "variaflow-worker-1")
    scheduler_max_inflight_tasks: int = _get_int("VARIAFLOW_SCHEDULER_MAX_INFLIGHT_TASKS", 1)
    provider_request_timeout_seconds: float = float(
        os.getenv("VARIAFLOW_PROVIDER_REQUEST_TIMEOUT_SECONDS", "90")
    )
    use_mock_ai: bool = (
        (_get_env("VARIAFLOW_USE_MOCK_AI", aliases=("USE_MOCK_AI",)) or "true").strip().lower()
        in {"1", "true", "yes", "on"}
    )
    mock_failure_rate: float = float(
        _get_env("VARIAFLOW_MOCK_FAILURE_RATE", "0.3", aliases=("MOCK_FAILURE_RATE",)) or "0.3"
    )
    openai_image_2_url: str = _get_env(
        "VARIAFLOW_OPENAI_IMAGE_2_URL",
        "https://api.openai.com/v1/images/generations",
        aliases=("OPENAI_BASE_URL",),
    ) or "https://api.openai.com/v1/images/generations"
    openai_image_2_model: str = _get_env(
        "VARIAFLOW_OPENAI_IMAGE_2_MODEL",
        "image-2",
        aliases=("OPENAI_IMAGE_MODEL",),
    ) or "image-2"
    openai_image_2_api_key: str = _get_env(
        "VARIAFLOW_OPENAI_IMAGE_2_API_KEY",
        "",
        aliases=("OPENAI_API_KEY",),
    ) or ""
    aliyun_wanx_url: str = _get_env(
        "VARIAFLOW_ALIYUN_WANX_URL",
        "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis",
        aliases=("WANX_BASE_URL",),
    ) or "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis"
    aliyun_wanx_api_key: str = _get_env(
        "VARIAFLOW_ALIYUN_WANX_API_KEY",
        "",
        aliases=("WANX_API_KEY", "DASHSCOPE_API_KEY"),
    ) or ""


settings = Settings()
