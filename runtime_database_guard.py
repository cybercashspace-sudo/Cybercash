"""Keep local backend processes on one PostgreSQL database.

The app has async runtime code and some sync maintenance/migration paths. Both
must point at the same PostgreSQL database so wallets, ledgers, users, agents,
and admin balances never split across an old fallback database.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urlsplit, urlunsplit


DEFAULT_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5433/cybercash"
DEFAULT_SYNC_DATABASE_URL = "postgresql://postgres:postgres@127.0.0.1:5433/cybercash"
REQUIRED_LOCAL_DATABASE = "cybercash"

_FALSE_VALUES = {"0", "false", "off", "no", "disabled"}
_ENV_FILE = Path(__file__).resolve().parent / ".env"


def install() -> None:
    """Normalize local database environment variables before app config loads."""

    if os.getenv("CYBERCASH_DATABASE_GUARD", "1").strip().lower() in _FALSE_VALUES:
        return

    env_values = _read_env_values(_ENV_FILE)
    database_url = os.environ.get("DATABASE_URL") or env_values.get("DATABASE_URL")

    if _is_old_or_duplicate_database_url(database_url):
        database_url = DEFAULT_DATABASE_URL
    else:
        database_url = _ensure_async_postgres_driver(database_url)

    sync_database_url = (
        os.environ.get("SYNC_DATABASE_URL") or env_values.get("SYNC_DATABASE_URL")
    )
    derived_sync_url = _derive_sync_url(database_url)

    if (
        _is_old_or_duplicate_database_url(sync_database_url)
        or not _same_database_target(database_url, sync_database_url)
    ):
        sync_database_url = derived_sync_url

    os.environ["DATABASE_URL"] = database_url
    os.environ["SYNC_DATABASE_URL"] = sync_database_url


def _read_env_values(path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return values

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        values[key] = _strip_quotes(value.strip())
    return values


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _is_old_or_duplicate_database_url(url: Optional[str]) -> bool:
    if not url:
        return True

    lower = url.strip().lower()
    if lower.startswith("sqlite") or lower.endswith(".db"):
        return True
    if lower.startswith("postgres://"):
        return _is_wrong_local_database(url)
    if not lower.startswith("postgresql"):
        return True
    return _is_wrong_local_database(url)


def _ensure_async_postgres_driver(url: Optional[str]) -> str:
    if not url:
        return DEFAULT_DATABASE_URL

    parts = urlsplit(url)
    if parts.scheme == "postgresql+asyncpg":
        return url
    if parts.scheme in {"postgres", "postgresql"}:
        return urlunsplit(
            ("postgresql+asyncpg", parts.netloc, parts.path, parts.query, parts.fragment)
        )
    return DEFAULT_DATABASE_URL


def _derive_sync_url(async_url: str) -> str:
    parts = urlsplit(async_url)
    if parts.scheme.startswith("postgresql+") or parts.scheme == "postgres":
        return urlunsplit(("postgresql", parts.netloc, parts.path, parts.query, parts.fragment))
    if parts.scheme == "postgresql":
        return async_url
    return DEFAULT_SYNC_DATABASE_URL


def _same_database_target(left: Optional[str], right: Optional[str]) -> bool:
    if not left or not right:
        return False

    left_parts = urlsplit(left)
    right_parts = urlsplit(right)
    return (
        _base_scheme(left_parts.scheme) == _base_scheme(right_parts.scheme)
        and left_parts.hostname == right_parts.hostname
        and left_parts.port == right_parts.port
        and left_parts.username == right_parts.username
        and left_parts.path == right_parts.path
    )


def _is_wrong_local_database(url: str) -> bool:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    database = parts.path.lstrip("/").split("/", 1)[0]
    return host in {"127.0.0.1", "localhost"} and database != REQUIRED_LOCAL_DATABASE


def _base_scheme(scheme: str) -> str:
    if scheme.startswith("postgres"):
        return "postgresql"
    return scheme


install()
