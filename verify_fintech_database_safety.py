"""Verify CYBER CASH database safety settings and duplicate inputs.

This script checks that async and sync database URLs target the same PostgreSQL
database, then audits common account, wallet, and ledger tables for duplicate
business keys. It reports duplicates; it does not delete live money records.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import unquote, urlsplit, urlunsplit


DEFAULT_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5433/cybercash"
DEFAULT_SYNC_DATABASE_URL = "postgresql://postgres:postgres@127.0.0.1:5433/cybercash"
REQUIRED_LOCAL_DATABASE = "cybercash"

ACCOUNT_TABLE_HINTS = ("user", "agent", "admin", "customer")
WALLET_TABLE_HINTS = ("wallet", "account", "balance")
LEDGER_TABLE_HINTS = ("transaction", "ledger", "transfer", "deposit", "withdrawal")

BUSINESS_KEY_COLUMNS = (
    "phone",
    "phone_number",
    "mobile",
    "email",
    "username",
    "account_number",
    "wallet_number",
    "reference",
    "transaction_id",
    "external_reference",
    "paystack_reference",
)
OWNER_KEY_COLUMNS = ("user_id", "agent_id", "admin_id", "customer_id", "owner_id")
MONEY_COLUMNS = (
    "balance",
    "wallet_balance",
    "available_balance",
    "pending_balance",
    "float_balance",
    "commission_balance",
    "system_balance",
)


@dataclass(frozen=True)
class TableRef:
    schema: str
    name: str

    @property
    def label(self) -> str:
        return f"{self.schema}.{self.name}"


@dataclass(frozen=True)
class DuplicateFinding:
    table: TableRef
    column: str
    value: str
    count: int


@dataclass(frozen=True)
class MoneyFinding:
    table: TableRef
    column: str
    issue: str
    count: int


def main() -> int:
    env_values = _read_env_values(Path(__file__).resolve().parent / ".env")
    database_url = os.environ.get("DATABASE_URL") or env_values.get(
        "DATABASE_URL", DEFAULT_DATABASE_URL
    )
    sync_database_url = os.environ.get("SYNC_DATABASE_URL") or env_values.get(
        "SYNC_DATABASE_URL", DEFAULT_SYNC_DATABASE_URL
    )

    database_url = _normalize_async_url(database_url)
    sync_database_url = _normalize_sync_url(sync_database_url)

    _verify_url_pair(database_url, sync_database_url)
    print("Database URLs verified:")
    print(f"- DATABASE_URL={_mask_password(database_url)}")
    print(f"- SYNC_DATABASE_URL={_mask_password(sync_database_url)}")

    rows = _query_rows(sync_database_url, "SELECT current_database(), current_user")
    current_database, current_user = rows[0]
    print(f"Connected to PostgreSQL database {current_database!r} as {current_user!r}.")

    tables = _load_candidate_tables(sync_database_url)
    if not tables:
        print("No account/wallet/ledger tables found yet. Schema may not be migrated.")
        return 0

    duplicate_findings = _audit_duplicate_business_keys(sync_database_url, tables)
    money_findings = _audit_money_columns(sync_database_url, tables)

    _print_audit_results(duplicate_findings, money_findings)
    if duplicate_findings or money_findings:
        print(
            "Verification found records needing review. No live money records were "
            "deleted automatically."
        )
        return 3

    print("No duplicate account/wallet/ledger inputs or invalid money values found.")
    return 0


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


def _verify_url_pair(database_url: str, sync_database_url: str) -> None:
    database_parts = urlsplit(database_url)
    sync_parts = urlsplit(sync_database_url)
    database_name = _database_name(sync_database_url)

    if database_name != REQUIRED_LOCAL_DATABASE:
        raise ValueError(
            f"Expected database {REQUIRED_LOCAL_DATABASE!r}, got {database_name!r}."
        )
    if not _same_database_target(database_parts, sync_parts):
        raise ValueError("DATABASE_URL and SYNC_DATABASE_URL do not target the same database.")


def _database_name(url: str) -> str:
    database = unquote(urlsplit(url).path.lstrip("/")).split("/", 1)[0]
    if not database:
        raise ValueError("Database URL must include a database name.")
    return database


def _same_database_target(left, right) -> bool:
    return (
        _base_scheme(left.scheme) == _base_scheme(right.scheme)
        and left.hostname == right.hostname
        and left.port == right.port
        and left.username == right.username
        and left.path == right.path
    )


def _base_scheme(scheme: str) -> str:
    return "postgresql" if scheme.startswith("postgres") else scheme


def _mask_password(url: str) -> str:
    parts = urlsplit(url)
    if parts.password is None:
        return url
    username = unquote(parts.username or "")
    host = parts.hostname or ""
    port = f":{parts.port}" if parts.port else ""
    netloc = f"{username}:***@{host}{port}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def _load_candidate_tables(sync_url: str) -> List[TableRef]:
    hints = ACCOUNT_TABLE_HINTS + WALLET_TABLE_HINTS + LEDGER_TABLE_HINTS
    like_clauses = " OR ".join(["lower(table_name) LIKE %s" for _ in hints])
    sql = (
        "SELECT table_schema, table_name FROM information_schema.tables "
        "WHERE table_type = 'BASE TABLE' AND table_schema NOT IN "
        "('pg_catalog', 'information_schema') AND "
        f"({like_clauses}) ORDER BY table_schema, table_name"
    )
    rows = _query_rows(sync_url, sql, tuple(f"%{hint}%" for hint in hints))
    return [TableRef(schema=str(row[0]), name=str(row[1])) for row in rows]


def _audit_duplicate_business_keys(
    sync_url: str,
    tables: Sequence[TableRef],
) -> List[DuplicateFinding]:
    findings: List[DuplicateFinding] = []
    for table in tables:
        columns = _load_columns(sync_url, table)
        key_columns = [column for column in BUSINESS_KEY_COLUMNS if column in columns]
        if _looks_like_wallet_table(table.name):
            key_columns.extend(column for column in OWNER_KEY_COLUMNS if column in columns)

        for column in dict.fromkeys(key_columns):
            rows = _duplicate_rows(sync_url, table, column)
            for value, count in rows:
                findings.append(
                    DuplicateFinding(
                        table=table,
                        column=column,
                        value=str(value),
                        count=int(count),
                    )
                )
    return findings


def _audit_money_columns(sync_url: str, tables: Sequence[TableRef]) -> List[MoneyFinding]:
    findings: List[MoneyFinding] = []
    for table in tables:
        columns = _load_columns(sync_url, table)
        for column in MONEY_COLUMNS:
            if column not in columns:
                continue
            null_count = _scalar_count(
                sync_url,
                f"SELECT count(*) FROM {_quote_table(table)} WHERE {_quote_identifier(column)} IS NULL",
            )
            if null_count:
                findings.append(MoneyFinding(table, column, "NULL money value", null_count))

            negative_count = _scalar_count(
                sync_url,
                f"SELECT count(*) FROM {_quote_table(table)} WHERE {_quote_identifier(column)} < 0",
            )
            if negative_count:
                findings.append(MoneyFinding(table, column, "negative money value", negative_count))
    return findings


def _looks_like_wallet_table(table_name: str) -> bool:
    lower = table_name.lower()
    return any(hint in lower for hint in WALLET_TABLE_HINTS)


def _load_columns(sync_url: str, table: TableRef) -> List[str]:
    sql = (
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = %s AND table_name = %s ORDER BY ordinal_position"
    )
    rows = _query_rows(sync_url, sql, (table.schema, table.name))
    return [str(row[0]) for row in rows]


def _duplicate_rows(sync_url: str, table: TableRef, column: str) -> List[Tuple[object, int]]:
    sql = (
        f"SELECT {_quote_identifier(column)}, count(*) FROM {_quote_table(table)} "
        f"WHERE {_quote_identifier(column)} IS NOT NULL "
        f"GROUP BY {_quote_identifier(column)} HAVING count(*) > 1 "
        "ORDER BY count(*) DESC LIMIT 20"
    )
    return [(row[0], int(row[1])) for row in _query_rows(sync_url, sql)]


def _scalar_count(sync_url: str, sql: str) -> int:
    rows = _query_rows(sync_url, sql)
    return int(rows[0][0]) if rows else 0


def _query_rows(
    sync_url: str,
    sql: str,
    params: Optional[Sequence[object]] = None,
) -> List[Tuple[object, ...]]:
    driver = _load_driver()
    if driver is not None:
        driver_name, module = driver
        if driver_name == "psycopg":
            conn = module.connect(sync_url, autocommit=True, connect_timeout=5)
        else:
            conn = module.connect(sync_url, connect_timeout=5)
            conn.autocommit = True
        try:
            with conn.cursor() as cursor:
                cursor.execute(sql, tuple(params or ()))
                return list(cursor.fetchall())
        finally:
            conn.close()

    return _query_rows_with_psql(sync_url, sql, params)


def _load_driver() -> Optional[Tuple[str, object]]:
    for driver_name in ("psycopg", "psycopg2"):
        try:
            return driver_name, __import__(driver_name)
        except Exception:
            continue
    return None


def _query_rows_with_psql(
    sync_url: str,
    sql: str,
    params: Optional[Sequence[object]],
) -> List[Tuple[object, ...]]:
    if params:
        raise RuntimeError("psql fallback does not support parameterized audit queries.")
    output = _run_psql(_psql_base_args(sync_url) + [sql], _psql_env(sync_url))
    rows: List[Tuple[object, ...]] = []
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(tuple(part.strip() for part in line.split("|")))
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
        _database_name(url),
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


def _postgres_tool(name: str) -> Optional[str]:
    found = shutil.which(name)
    if found:
        return found

    for version in ("18", "17", "16", "15", "14", "13", "12"):
        candidate = Path("C:/Program Files/PostgreSQL") / version / "bin" / f"{name}.exe"
        if candidate.exists():
            return str(candidate)
    return None


def _quote_table(table: TableRef) -> str:
    return f"{_quote_identifier(table.schema)}.{_quote_identifier(table.name)}"


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _print_audit_results(
    duplicate_findings: Sequence[DuplicateFinding],
    money_findings: Sequence[MoneyFinding],
) -> None:
    if duplicate_findings:
        print()
        print("Duplicate account/wallet/ledger input findings:")
        for finding in duplicate_findings:
            print(
                f"- {finding.table.label}.{finding.column} value={finding.value!r} "
                f"count={finding.count}"
            )

    if money_findings:
        print()
        print("Money value findings:")
        for finding in money_findings:
            print(
                f"- {finding.table.label}.{finding.column}: "
                f"{finding.issue} count={finding.count}"
            )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Fintech database safety verification failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
