from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

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


def _normalize_openai_image_edit_url(value: str | None) -> str:
    default_url = "https://api.openai.com/v1/images/edits"
    if value is None:
        return default_url

    normalized = value.strip()
    if not normalized:
        return default_url

    lower = normalized.lower().rstrip("/")
    if lower.endswith("/images/edits"):
        return normalized.rstrip("/")
    if lower.endswith("/v1"):
        return normalized.rstrip("/") + "/images/edits"

    parsed = urlsplit(normalized)
    if not parsed.scheme or not parsed.netloc:
        return normalized

    path = parsed.path.rstrip("/")
    if path in {"", "/"}:
        path = "/v1/images/edits"
    else:
        path = f"{path}/images/edits"

    return urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, parsed.fragment))


def _normalize_chat_completions_url(value: str | None) -> str:
    default_url = "https://www.onetopai.asia/v1/chat/completions"
    if value is None:
        return default_url

    normalized = value.strip()
    if not normalized:
        return default_url

    lower = normalized.lower().rstrip("/")
    if lower.endswith("/chat/completions"):
        return normalized.rstrip("/")
    if lower.endswith("/v1"):
        return normalized.rstrip("/") + "/chat/completions"

    parsed = urlsplit(normalized)
    if not parsed.scheme or not parsed.netloc:
        return normalized

    path = parsed.path.rstrip("/")
    if path in {"", "/"}:
        path = "/v1/chat/completions"
    else:
        path = f"{path}/chat/completions"

    return urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, parsed.fragment))


def _normalize_openai_image_generation_url(value: str | None) -> str:
    default_url = "https://api.openai.com/v1/images/generations"
    if value is None:
        return default_url

    normalized = value.strip()
    if not normalized:
        return default_url

    lower = normalized.lower().rstrip("/")
    if lower.endswith("/images/generations"):
        return normalized.rstrip("/")
    if lower.endswith("/images/edits"):
        return normalized.rstrip("/")[: -len("/images/edits")] + "/images/generations"
    if lower.endswith("/v1"):
        return normalized.rstrip("/") + "/images/generations"

    parsed = urlsplit(normalized)
    if not parsed.scheme or not parsed.netloc:
        return normalized

    path = parsed.path.rstrip("/")
    if path in {"", "/"}:
        path = "/v1/images/generations"
    else:
        path = f"{path}/images/generations"

    return urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, parsed.fragment))


def _get_openai_image_generation_url() -> str:
    explicit_generation_url = _get_env(
        "VARIAFLOW_OPENAI_IMAGE_GENERATION_URL",
        aliases=("VARIAFLOW_OPENAI_IMAGE_2_URL",),
    )
    if explicit_generation_url is not None:
        return _normalize_openai_image_generation_url(explicit_generation_url)

    edit_url = _get_env(
        "VARIAFLOW_OPENAI_IMAGE_EDIT_URL",
        "https://api.openai.com/v1/images/edits",
        aliases=("OPENAI_BASE_URL",),
    )
    return _normalize_openai_image_generation_url(edit_url)


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


def _get_vision_api_key() -> str:
    return (
        _get_env(
            "VARIAFLOW_VISION_API_KEY",
            "",
            aliases=("VARIAFLOW_OPENAI_IMAGE_API_KEY", "OPENAI_API_KEY"),
        )
        or ""
    )


def _get_vision_provider() -> str:
    return (_get_env("VARIAFLOW_VISION_PROVIDER", "mimo") or "mimo").strip().lower()


def _get_effective_vision_api_url() -> str:
    provider = _get_vision_provider()
    if provider == "deepseek":
        return _normalize_chat_completions_url(
            _get_env(
                "VARIAFLOW_DEEPSEEK_VISION_API_URL",
                "https://api.deepseek.com/v1/chat/completions",
            )
        )
    if provider == "mimo":
        return _normalize_chat_completions_url(
            _get_env(
                "VARIAFLOW_MIMO_VISION_API_URL",
                "https://token-plan-cn.xiaomimimo.com/v1/chat/completions",
            )
        )
    return _normalize_chat_completions_url(
        _get_env(
            "VARIAFLOW_VISION_API_URL",
            "https://www.onetopai.asia/v1/chat/completions",
        )
    )


def _get_effective_vision_model() -> str:
    provider = _get_vision_provider()
    if provider == "deepseek":
        return (
            _get_env(
                "VARIAFLOW_DEEPSEEK_VISION_MODEL",
                "deepseek-v4-flash",
            )
            or "deepseek-v4-flash"
        )
    if provider == "mimo":
        return (
            _get_env(
                "VARIAFLOW_MIMO_VISION_MODEL",
                "mimo-v2-omni",
            )
            or "mimo-v2-omni"
        )
    return _get_env(
        "VARIAFLOW_VISION_MODEL",
        "mimo-v2-omni",
    ) or "mimo-v2-omni"


def _get_effective_vision_api_key() -> str:
    provider = _get_vision_provider()
    if provider == "deepseek":
        return (
            _get_env(
                "VARIAFLOW_DEEPSEEK_VISION_API_KEY",
                "",
            )
            or ""
        )
    if provider == "mimo":
        return (
            _get_env(
                "VARIAFLOW_MIMO_VISION_API_KEY",
                "",
            )
            or ""
        )
    return _get_vision_api_key()


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
    db_supports_skip_locked: bool = _get_bool("VARIAFLOW_DB_SUPPORTS_SKIP_LOCKED", False)
    provider_debug_log: bool = _get_bool("VARIAFLOW_PROVIDER_DEBUG_LOG", False)
    provider_request_timeout_seconds: float = float(
        os.getenv("VARIAFLOW_PROVIDER_REQUEST_TIMEOUT_SECONDS", "90")
    )
    provider_enable_fallback: bool = _get_bool("VARIAFLOW_PROVIDER_ENABLE_FALLBACK", False)
    qc_min_file_size_bytes: int = _get_int("VARIAFLOW_QC_MIN_FILE_SIZE_BYTES", 51_200)
    qc_min_width: int = _get_int("VARIAFLOW_QC_MIN_WIDTH", 768)
    qc_min_height: int = _get_int("VARIAFLOW_QC_MIN_HEIGHT", 752)
    qc_min_total_pixels: int = _get_int("VARIAFLOW_QC_MIN_TOTAL_PIXELS", 577_536)
    aliyun_use_sdk_for_imageedit: bool = _get_bool("VARIAFLOW_ALIYUN_USE_SDK_FOR_IMAGEEDIT", True)
    image_provider: str = (_get_env("VARIAFLOW_IMAGE_PROVIDER", "openai") or "openai").strip().lower()
    use_mock_ai: bool = (
        (_get_env("VARIAFLOW_USE_MOCK_AI", aliases=("USE_MOCK_AI",)) or "true").strip().lower()
        in {"1", "true", "yes", "on"}
    )
    mock_failure_rate: float = float(
        _get_env("VARIAFLOW_MOCK_FAILURE_RATE", "0.3", aliases=("MOCK_FAILURE_RATE",)) or "0.3"
    )
    openai_image_edit_url: str = _normalize_openai_image_edit_url(
        _get_env(
            "VARIAFLOW_OPENAI_IMAGE_EDIT_URL",
            "https://api.openai.com/v1/images/edits",
            aliases=("OPENAI_BASE_URL", "VARIAFLOW_OPENAI_IMAGE_2_URL"),
        )
    )
    openai_image_model: str = _get_env(
        "VARIAFLOW_OPENAI_IMAGE_MODEL",
        "gpt-image-2",
        aliases=("OPENAI_IMAGE_MODEL", "VARIAFLOW_OPENAI_IMAGE_2_MODEL"),
    ) or "gpt-image-2"
    openai_image_generation_url: str = field(default_factory=_get_openai_image_generation_url)
    openai_image_api_key: str = _get_env(
        "VARIAFLOW_OPENAI_IMAGE_API_KEY",
        "",
        aliases=("OPENAI_API_KEY", "VARIAFLOW_OPENAI_IMAGE_2_API_KEY"),
    ) or ""
    vision_router_enabled: bool = _get_bool("VARIAFLOW_VISION_ROUTER_ENABLED", True)
    vision_provider: str = field(default_factory=_get_vision_provider)
    vision_api_url: str = field(default_factory=_get_effective_vision_api_url)
    vision_model: str = field(default_factory=_get_effective_vision_model)
    vision_api_key: str = field(default_factory=_get_effective_vision_api_key)
    vision_request_timeout_seconds: float = _get_float(
        "VARIAFLOW_VISION_REQUEST_TIMEOUT_SECONDS",
        45.0,
    )
    vision_default_intent: str = (
        _get_env("VARIAFLOW_VISION_DEFAULT_INTENT", "SCENE_EDIT") or "SCENE_EDIT"
    ).strip().upper()
    aliyun_wanx_url: str = _get_env(
        "VARIAFLOW_ALIYUN_WANX_URL",
        "https://dashscope.aliyuncs.com/api/v1/services/aigc/image-generation/generation",
        aliases=("WANX_BASE_URL",),
    ) or "https://dashscope.aliyuncs.com/api/v1/services/aigc/image-generation/generation"
    aliyun_wanx_imageedit_url: str = _get_env(
        "VARIAFLOW_ALIYUN_WANX_IMAGEEDIT_URL",
        "https://dashscope.aliyuncs.com/api/v1/services/aigc/image2image/image-synthesis",
    ) or "https://dashscope.aliyuncs.com/api/v1/services/aigc/image2image/image-synthesis"
    aliyun_wanx_model: str = _get_env(
        "VARIAFLOW_ALIYUN_WANX_MODEL",
        "wan2.7-image-pro",
        aliases=("WANX_MODEL",),
    ) or "wan2.7-image-pro"
    aliyun_imageedit_function: str = _get_env(
        "VARIAFLOW_ALIYUN_IMAGEEDIT_FUNCTION",
        "description_edit",
    ) or "description_edit"
    aliyun_imageedit_strength: float = _get_float(
        "VARIAFLOW_ALIYUN_IMAGEEDIT_STRENGTH",
        0.85,
    )
    aliyun_wanx_api_key: str = _get_env(
        "VARIAFLOW_ALIYUN_WANX_API_KEY",
        "",
        aliases=("WANX_API_KEY", "DASHSCOPE_API_KEY"),
    ) or ""


settings = Settings()
