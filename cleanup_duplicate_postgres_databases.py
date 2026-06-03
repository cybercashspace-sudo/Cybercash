"""Find and optionally remove old duplicate local PostgreSQL databases.

The live CYBER CASH database is `cybercash`. This tool is deliberately
destructive only when a database name and confirmation phrase are supplied.
It never drops the live target database.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import unquote, urlsplit, urlunsplit


DEFAULT_SYNC_DATABASE_URL = "postgresql://postgres:postgres@127.0.0.1:5433/cybercash"
LIVE_DATABASE = "cybercash"
CONFIRM_PHRASE = "DELETE_OLD_DUPLICATE_DATABASE"
PROTECTED_DATABASES = {"postgres", "template0", "template1", LIVE_DATABASE}


@dataclass(frozen=True)
class DatabaseInfo:
    name: str
    owner: str
    size: str
    active_connections: int


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    env_values = _read_env_values(Path(__file__).resolve().parent / ".env")
    sync_url = os.environ.get("SYNC_DATABASE_URL") or env_values.get(
        "SYNC_DATABASE_URL", DEFAULT_SYNC_DATABASE_URL
    )
    sync_url = _normalize_sync_url(sync_url)

    target_name = _database_name(sync_url)
    if target_name != LIVE_DATABASE:
        print(
            f"Refusing cleanup because configured database is {target_name!r}, "
            f"not the required live database {LIVE_DATABASE!r}.",
            file=sys.stderr,
        )
        return 2

    maintenance_url = _maintenance_url(sync_url)
    databases = _list_databases(maintenance_url)
    duplicates = _duplicate_candidates(databases)

    _print_database_report(databases, duplicates)

    if not args.drop:
        print()
        print("No database was deleted. To delete a duplicate, rerun with:")
        print(
            "python cleanup_duplicate_postgres_databases.py "
            f"--drop OLD_DB_NAME --confirm {CONFIRM_PHRASE}"
        )
        return 0

    return _drop_duplicate_database(maintenance_url, databases, duplicates, args)


def _parse_args(argv: Optional[Sequence[str]]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="List and safely drop old duplicate CYBER CASH PostgreSQL databases."
    )
    parser.add_argument(
        "--drop",
        metavar="DATABASE",
        help="Exact old duplicate database name to drop. The live cybercash database is protected.",
    )
    parser.add_argument(
        "--confirm",
        help=f"Required confirmation phrase for deleting a duplicate: {CONFIRM_PHRASE}",
    )
    parser.add_argument(
        "--allow-drop-without-backup",
        action="store_true",
        help="Allow deletion when pg_dump is unavailable. Use only after manual backup.",
    )
    return parser.parse_args(argv)


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


def _normalize_sync_url(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme in {"postgres", "postgresql+asyncpg"}:
        return urlunsplit(("postgresql", parts.netloc, parts.path, parts.query, parts.fragment))
    if parts.scheme == "postgresql":
        return url
    raise ValueError(f"Refusing unsupported PostgreSQL URL scheme: {parts.scheme!r}")


def _database_name(url: str) -> str:
    database = unquote(urlsplit(url).path.lstrip("/")).split("/", 1)[0]
    if not database:
        raise ValueError("SYNC_DATABASE_URL must include a database name.")
    return database


def _maintenance_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit(("postgresql", parts.netloc, "/postgres", parts.query, parts.fragment))


def _list_databases(maintenance_url: str) -> List[DatabaseInfo]:
    sql = (
        "SELECT datname, pg_catalog.pg_get_userbyid(datdba), "
        "pg_size_pretty(pg_database_size(datname)), "
        "(SELECT count(*) FROM pg_stat_activity WHERE datname = d.datname) "
        "FROM pg_database d WHERE datistemplate = false ORDER BY datname"
    )
    rows = _query_rows(maintenance_url, sql)
    return [
        DatabaseInfo(
            name=str(row[0]),
            owner=str(row[1]),
            size=str(row[2]),
            active_connections=int(row[3]),
        )
        for row in rows
    ]


def _query_rows(maintenance_url: str, sql: str) -> List[Tuple[object, ...]]:
    driver = _load_driver()
    if driver is not None:
        driver_name, module = driver
        if driver_name == "psycopg":
            conn = module.connect(maintenance_url, autocommit=True, connect_timeout=5)
        else:
            conn = module.connect(maintenance_url, connect_timeout=5)
            conn.autocommit = True
        try:
            with conn.cursor() as cursor:
                cursor.execute(sql)
                return list(cursor.fetchall())
        finally:
            conn.close()

    return _query_rows_with_psql(maintenance_url, sql)


def _execute(maintenance_url: str, sql: str) -> None:
    driver = _load_driver()
    if driver is not None:
        driver_name, module = driver
        if driver_name == "psycopg":
            conn = module.connect(maintenance_url, autocommit=True, connect_timeout=5)
        else:
            conn = module.connect(maintenance_url, connect_timeout=5)
            conn.autocommit = True
        try:
            with conn.cursor() as cursor:
                cursor.execute(sql)
        finally:
            conn.close()
        return

    _run_psql(_psql_base_args(maintenance_url) + [sql], _psql_env(maintenance_url))


def _load_driver() -> Optional[Tuple[str, object]]:
    for driver_name in ("psycopg", "psycopg2"):
        try:
            return driver_name, __import__(driver_name)
        except Exception:
            continue
    return None


def _query_rows_with_psql(maintenance_url: str, sql: str) -> List[Tuple[object, ...]]:
    output = _run_psql(
        _psql_base_args(maintenance_url) + [sql],
        _psql_env(maintenance_url),
    )
    rows: List[Tuple[object, ...]] = []
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [part.strip() for part in line.split("|")]
        rows.append(tuple(parts))
    return rows


def _psql_base_args(url: str) -> List[str]:
    parts = urlsplit(url)
    psql = _postgres_tool("psql")
    if psql is None:
        raise RuntimeError("No PostgreSQL driver or psql command was found.")
    return [
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


def _psql_env(url: str) -> Dict[str, str]:
    parts = urlsplit(url)
    env = os.environ.copy()
    if parts.password:
        env["PGPASSWORD"] = unquote(parts.password)
    return env


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


def _duplicate_candidates(databases: Iterable[DatabaseInfo]) -> List[DatabaseInfo]:
    candidates: List[DatabaseInfo] = []
    for database in databases:
        name = database.name.lower()
        if database.name in PROTECTED_DATABASES:
            continue
        compact = name.replace("_", "").replace("-", "")
        if "cybercash" in compact or "cyber" in compact and "cash" in compact:
            candidates.append(database)
    return candidates


def _print_database_report(
    databases: Sequence[DatabaseInfo],
    duplicates: Sequence[DatabaseInfo],
) -> None:
    print(f"Live database protected: {LIVE_DATABASE}")
    print()
    print("Local PostgreSQL databases:")
    for database in databases:
        marker = "LIVE" if database.name == LIVE_DATABASE else ""
        duplicate_marker = "DUPLICATE?" if database in duplicates else marker
        suffix = f" [{duplicate_marker}]" if duplicate_marker else ""
        print(
            f"- {database.name} owner={database.owner} "
            f"size={database.size} active_connections={database.active_connections}{suffix}"
        )


def _drop_duplicate_database(
    maintenance_url: str,
    databases: Sequence[DatabaseInfo],
    duplicates: Sequence[DatabaseInfo],
    args: argparse.Namespace,
) -> int:
    requested = args.drop
    if requested in PROTECTED_DATABASES:
        print(f"Refusing to delete protected database {requested!r}.", file=sys.stderr)
        return 2

    database_by_name = {database.name: database for database in databases}
    if requested not in database_by_name:
        print(f"Database {requested!r} was not found on this server.", file=sys.stderr)
        return 2

    duplicate_names = {database.name for database in duplicates}
    if requested not in duplicate_names:
        print(
            f"Database {requested!r} does not look like a CYBER CASH duplicate. "
            "Refusing automatic deletion.",
            file=sys.stderr,
        )
        return 2

    if args.confirm != CONFIRM_PHRASE:
        print(
            f"Refusing deletion. Pass --confirm {CONFIRM_PHRASE} to delete "
            "a verified old duplicate database.",
            file=sys.stderr,
        )
        return 2

    backup_path = _backup_database(maintenance_url, requested)
    if backup_path is None and not args.allow_drop_without_backup:
        print(
            "Refusing deletion because pg_dump is unavailable and no backup was created. "
            "Install PostgreSQL client tools or pass --allow-drop-without-backup only "
            "after making a manual backup.",
            file=sys.stderr,
        )
        return 2

    _execute(
        maintenance_url,
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
        f"WHERE datname = '{_quote_literal(requested)}' AND pid <> pg_backend_pid()",
    )
    _execute(maintenance_url, f"DROP DATABASE {_quote_identifier(requested)}")
    print(f"Deleted old duplicate database {requested!r}.")
    if backup_path is not None:
        print(f"Backup saved to {backup_path}")
    return 0


def _backup_database(maintenance_url: str, database: str) -> Optional[Path]:
    pg_dump = _postgres_tool("pg_dump")
    if pg_dump is None:
        return None

    parts = urlsplit(maintenance_url)
    backup_dir = Path(__file__).resolve().parent / "backups" / "postgres_database_backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = backup_dir / f"{database}-{timestamp}.sql"

    env = _psql_env(maintenance_url)
    args = [
        pg_dump,
        "-h",
        parts.hostname or "127.0.0.1",
        "-p",
        str(parts.port or 5432),
        "-U",
        unquote(parts.username or "postgres"),
        "-d",
        database,
        "-f",
        str(backup_path),
    ]
    subprocess.run(args, check=True, env=env)
    return backup_path


def _postgres_tool(name: str) -> Optional[str]:
    found = shutil.which(name)
    if found:
        return found

    for version in ("18", "17", "16", "15", "14", "13", "12"):
        candidate = Path("C:/Program Files/PostgreSQL") / version / "bin" / f"{name}.exe"
        if candidate.exists():
            return str(candidate)
    return None


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _quote_literal(value: str) -> str:
    return value.replace("'", "''")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Duplicate database cleanup failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
