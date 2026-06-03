"""Create the configured PostgreSQL database if it is missing.

This script is intentionally conservative: it creates only the exact database
target from DATABASE_URL/SYNC_DATABASE_URL and refuses old fallback databases
such as SQLite. It never drops, truncates, or resets money data.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional, Sequence
from urllib.parse import unquote, urlsplit, urlunsplit


DEFAULT_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5433/cybercash"
DEFAULT_SYNC_DATABASE_URL = "postgresql://postgres:postgres@127.0.0.1:5433/cybercash"
REQUIRED_LOCAL_DATABASE = "cybercash"


def main() -> int:
    env_values = _read_env_values(Path(__file__).resolve().parent / ".env")
    database_url = os.environ.get("DATABASE_URL") or env_values.get("DATABASE_URL")
    sync_database_url = os.environ.get("SYNC_DATABASE_URL") or env_values.get(
        "SYNC_DATABASE_URL"
    )

    database_url = _normalize_async_url(database_url or DEFAULT_DATABASE_URL)
    sync_database_url = _normalize_sync_url(
        sync_database_url or _derive_sync_url(database_url) or DEFAULT_SYNC_DATABASE_URL
    )

    if not _same_database_target(database_url, sync_database_url):
        print(
            "DATABASE_URL and SYNC_DATABASE_URL point to different targets. "
            "Refusing to create a duplicate/old database.",
            file=sys.stderr,
        )
        print(f"DATABASE_URL={database_url}", file=sys.stderr)
        print(f"SYNC_DATABASE_URL={sync_database_url}", file=sys.stderr)
        return 2

    target = _target_from_url(sync_database_url)
    if target.database != REQUIRED_LOCAL_DATABASE:
        print(
            f"Refusing to create database {target.database!r}. "
            f"Local CYBER CASH must use the single PostgreSQL database "
            f"{REQUIRED_LOCAL_DATABASE!r} to avoid duplicated wallets/balances.",
            file=sys.stderr,
        )
        return 2

    maintenance_url = _maintenance_url(sync_database_url)
    created = _ensure_with_python_driver(maintenance_url, target.database)
    if created is None:
        created = _ensure_with_psql(maintenance_url, target.database)

    if created is None:
        print(
            "Could not verify/create the PostgreSQL database because no usable "
            "Python PostgreSQL driver or psql command was found.",
            file=sys.stderr,
        )
        print("Install psycopg/psycopg2 or PostgreSQL client tools, then rerun.", file=sys.stderr)
        return 1

    if created:
        print(f"Created PostgreSQL database {target.database!r}.")
    else:
        print(f"PostgreSQL database {target.database!r} already exists.")
    print("Async and sync database URLs target the same database.")
    print(
        "To inspect or delete old duplicate local databases, run "
        "cleanup_duplicate_postgres_databases.ps1."
    )
    return 0


class Target:
    def __init__(self, database: str) -> None:
        self.database = database


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
        if key:
            values[key] = _strip_quotes(value.strip())
    return values


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _normalize_async_url(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme in {"postgres", "postgresql"}:
        return urlunsplit(
            ("postgresql+asyncpg", parts.netloc, parts.path, parts.query, parts.fragment)
        )
    if parts.scheme == "postgresql+asyncpg":
        return url
    raise ValueError(f"Refusing unsupported DATABASE_URL scheme: {parts.scheme!r}")


def _normalize_sync_url(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme in {"postgres", "postgresql+asyncpg"}:
        return urlunsplit(("postgresql", parts.netloc, parts.path, parts.query, parts.fragment))
    if parts.scheme == "postgresql":
        return url
    raise ValueError(f"Refusing unsupported SYNC_DATABASE_URL scheme: {parts.scheme!r}")


def _derive_sync_url(async_url: str) -> Optional[str]:
    parts = urlsplit(async_url)
    if parts.scheme in {"postgres", "postgresql", "postgresql+asyncpg"}:
        return urlunsplit(("postgresql", parts.netloc, parts.path, parts.query, parts.fragment))
    return None


def _same_database_target(left: str, right: str) -> bool:
    left_parts = urlsplit(left)
    right_parts = urlsplit(right)
    return (
        _base_scheme(left_parts.scheme) == _base_scheme(right_parts.scheme)
        and left_parts.hostname == right_parts.hostname
        and left_parts.port == right_parts.port
        and left_parts.username == right_parts.username
        and left_parts.path == right_parts.path
    )


def _base_scheme(scheme: str) -> str:
    return "postgresql" if scheme.startswith("postgres") else scheme


def _target_from_url(url: str) -> Target:
    parts = urlsplit(url)
    database = unquote(parts.path.lstrip("/")).split("/", 1)[0]
    if not database:
        raise ValueError("Database URL must include a database name.")
    return Target(database=database)


def _maintenance_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit(("postgresql", parts.netloc, "/postgres", parts.query, parts.fragment))


def _ensure_with_python_driver(maintenance_url: str, database: str) -> Optional[bool]:
    for driver_name in ("psycopg", "psycopg2"):
        try:
            driver = __import__(driver_name)
        except Exception:
            continue
        return _ensure_with_driver(driver_name, driver, maintenance_url, database)
    return None


def _ensure_with_driver(
    driver_name: str,
    driver: object,
    maintenance_url: str,
    database: str,
) -> bool:
    if driver_name == "psycopg":
        conn = driver.connect(maintenance_url, autocommit=True, connect_timeout=5)
    else:
        conn = driver.connect(maintenance_url, connect_timeout=5)
        conn.autocommit = True

    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (database,))
            if cursor.fetchone():
                return False
            cursor.execute(f"CREATE DATABASE {_quote_identifier(database)}")
            return True
    finally:
        conn.close()


def _ensure_with_psql(maintenance_url: str, database: str) -> Optional[bool]:
    psql = _postgres_tool("psql")
    if psql is None:
        return None

    parts = urlsplit(maintenance_url)
    password = unquote(parts.password or "")
    env = os.environ.copy()
    if password:
        env["PGPASSWORD"] = password

    base_args = [
        psql,
        "-h",
        parts.hostname or "127.0.0.1",
        "-p",
        str(parts.port or 5432),
        "-U",
        unquote(parts.username or "postgres"),
        "-d",
        "postgres",
        "-tAc",
    ]

    exists_sql = f"SELECT 1 FROM pg_database WHERE datname = '{_quote_literal(database)}'"
    exists = _run_psql(base_args + [exists_sql], env).strip()
    if exists == "1":
        return False

    _run_psql(base_args + [f"CREATE DATABASE {_quote_identifier(database)}"], env)
    return True


def _postgres_tool(name: str) -> Optional[str]:
    found = shutil.which(name)
    if found:
        return found

    for version in ("18", "17", "16", "15", "14", "13", "12"):
        candidate = Path("C:/Program Files/PostgreSQL") / version / "bin" / f"{name}.exe"
        if candidate.exists():
            return str(candidate)
    return None


def _run_psql(args: Sequence[str], env: Dict[str, str]) -> str:
    completed = subprocess.run(
        args,
        check=True,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _quote_literal(value: str) -> str:
    return value.replace("'", "''")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Database bootstrap failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
