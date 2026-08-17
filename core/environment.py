from __future__ import annotations

import json
import os
from enum import Enum
from pathlib import Path

try:
    from kivy.utils import platform as kivy_platform
except Exception:
    kivy_platform = ""

try:
    from dotenv import load_dotenv
except Exception:
    def load_dotenv(*_args, **_kwargs):
        return False


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Environment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


_RUNTIME_ENV_LOADED = False


def _is_mobile_platform() -> bool:
    return str(kivy_platform or "").strip().lower() in {"android", "ios"}


def load_runtime_environment() -> None:
    """Load local environment overrides once on desktop builds."""

    global _RUNTIME_ENV_LOADED
    if _RUNTIME_ENV_LOADED:
        return
    _RUNTIME_ENV_LOADED = True

    if _is_mobile_platform():
        return

    dotenv_path = PROJECT_ROOT / ".env"
    if dotenv_path.exists():
        try:
            load_dotenv(str(dotenv_path))
        except Exception:
            pass


def resolve_environment() -> Environment:
    load_runtime_environment()
    raw = str(os.getenv("CYBERCASH_ENV", os.getenv("APP_ENV", "development")) or "").strip().lower()
    if raw in {Environment.STAGING.value, "stage"}:
        return Environment.STAGING
    if raw in {Environment.PRODUCTION.value, "prod", "live"}:
        return Environment.PRODUCTION
    return Environment.DEVELOPMENT


def _normalize_url(raw_value: str) -> str:
    cleaned_value = str(raw_value or "").strip().rstrip("/")
    if not cleaned_value:
        return ""
    if "://" not in cleaned_value:
        cleaned_value = f"https://{cleaned_value}"
    return cleaned_value


def _load_app_config() -> dict:
    candidates = (
        PROJECT_ROOT / "app_config.json",
        Path.cwd() / "app_config.json",
    )
    for path in candidates:
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return payload
        except Exception:
            continue
    return {}


def _default_api_url(environment: Environment) -> str:
    if environment == Environment.STAGING:
        return "https://staging-api.cybercash.space"
    if environment == Environment.PRODUCTION:
        return "https://api.cybercash.space"
    if _is_mobile_platform():
        return "https://dev-api.cybercash.space"
    return "http://127.0.0.1:8000"


def resolve_api_base_url(environment: Environment | None = None) -> str:
    load_runtime_environment()
    env = environment or resolve_environment()

    for env_name in ("CYBERCASH_API_URL", "KIVY_API_URL", "BACKEND_URL"):
        value = _normalize_url(os.getenv(env_name, ""))
        if value:
            return value

    config = _load_app_config()
    for key in ("api_url", "backend_url", "base_url"):
        value = _normalize_url(config.get(key, ""))
        if value:
            return value

    return _normalize_url(_default_api_url(env))


def resolve_api_urls(environment: Environment | None = None) -> list[str]:
    load_runtime_environment()
    env = environment or resolve_environment()
    urls: list[str] = []

    def _append(value: str) -> None:
        normalized = _normalize_url(value)
        if normalized and normalized not in urls:
            urls.append(normalized)

    _append(resolve_api_base_url(env))

    legacy_urls = (
        "https://cybercash.space",
        "https://www.cybercash.space",
        "https://cyber-cash.onrender.com",
    )
    for value in legacy_urls:
        _append(value)

    return urls
