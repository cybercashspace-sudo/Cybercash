"""Runtime protection for real-money account data.

This module is intentionally small and dependency-light. It is loaded by
sitecustomize.py so technical updates cannot accidentally wipe user, agent, or
admin wallet data through destructive SQL.
"""

from __future__ import annotations

import os
import re
import sys
import threading
from typing import Any, Optional


_INSTALL_LOCK = threading.Lock()
_INSTALLED = False

_GUARD_ENV = "CYBERCASH_REAL_MONEY_SAFETY"
_OVERRIDE_ENV = "CYBERCASH_ALLOW_DESTRUCTIVE_MONEY_UPDATE"
_OVERRIDE_VALUE = "I_UNDERSTAND_THIS_CAN_LOSE_REAL_MONEY"

_FALSE_VALUES = {"0", "false", "off", "no", "disabled"}
_CRITICAL_TABLE = (
    r"(?:"
    r"users?|user_accounts?|"
    r"agents?|agent_accounts?|"
    r"admins?|admin_accounts?|"
    r"wallets?|accounts?|"
    r"transactions?|ledger(?:_entries)?|"
    r"deposits?|withdrawals?|transfers?|commissions?|"
    r"system_funds?|funds?|"
    r"\w*(?:wallet|transaction|ledger|deposit|withdrawal|transfer|commission|balance|fund)\w*"
    r")"
)
_MONEY_FIELD = (
    r"(?:"
    r"balance|wallet_balance|available_balance|pending_balance|"
    r"float_balance|commission_balance|system_balance|amount"
    r")"
)

_DROP_OR_TRUNCATE_RE = re.compile(
    rf"\b(?:drop\s+table|truncate(?:\s+table)?)\b[^;]*\b{_CRITICAL_TABLE}\b",
    re.IGNORECASE,
)
_DROP_CONTAINER_RE = re.compile(
    r"\bdrop\s+(?:schema|database)\b",
    re.IGNORECASE,
)
_DELETE_RE = re.compile(
    rf"\bdelete\s+from\s+(?:\w+\.)?{_CRITICAL_TABLE}\b",
    re.IGNORECASE,
)
_ALTER_DROP_MONEY_RE = re.compile(
    rf"\balter\s+table\s+(?:\w+\.)?{_CRITICAL_TABLE}\b[^;]*\bdrop\s+column\s+{_MONEY_FIELD}\b",
    re.IGNORECASE,
)
_MASS_MONEY_UPDATE_RE = re.compile(
    rf"\bupdate\s+(?:\w+\.)?{_CRITICAL_TABLE}\s+set\b(?P<set_clause>.*)",
    re.IGNORECASE | re.DOTALL,
)
_MONEY_FIELD_ASSIGN_RE = re.compile(
    rf"\b{_MONEY_FIELD}\b\s*=",
    re.IGNORECASE,
)
_ZERO_OR_NULL_MONEY_RE = re.compile(
    rf"\b{_MONEY_FIELD}\b\s*=\s*(?:0(?:\.0+)?|null)\b",
    re.IGNORECASE,
)


class MoneySafetyError(RuntimeError):
    """Raised when a technical update tries to clear protected funds."""


def install() -> None:
    """Install SQLAlchemy SQL guards if SQLAlchemy is available."""

    global _INSTALLED
    with _INSTALL_LOCK:
        if _INSTALLED:
            return
        _INSTALLED = True

        try:
            from sqlalchemy import event
            from sqlalchemy.engine import Engine
        except Exception:
            return

        @event.listens_for(Engine, "before_cursor_execute")
        def _guard_money_sql(
            conn: Any,
            cursor: Any,
            statement: Any,
            parameters: Any,
            context: Any,
            executemany: bool,
        ) -> None:
            _raise_if_destructive(statement)


def _raise_if_destructive(statement: Any) -> None:
    if not _guard_enabled():
        return

    sql = _normalize_sql(statement)
    if not sql:
        return

    reason = _destructive_reason(sql)
    if reason is None:
        return

    message = (
        "Blocked destructive money-data SQL: "
        f"{reason}. Real user, agent, admin, wallet, ledger, and transaction "
        "funds are protected during technical updates. To run an audited reset "
        f"or restore, set {_OVERRIDE_ENV}={_OVERRIDE_VALUE} for that one "
        "maintenance command only."
    )
    print(message, file=sys.stderr)
    raise MoneySafetyError(message)


def _guard_enabled() -> bool:
    if os.getenv(_OVERRIDE_ENV, "") == _OVERRIDE_VALUE:
        return False
    return os.getenv(_GUARD_ENV, "1").strip().lower() not in _FALSE_VALUES


def _normalize_sql(statement: Any) -> str:
    if isinstance(statement, bytes):
        statement = statement.decode("utf-8", "replace")
    if not isinstance(statement, str):
        statement = str(statement)

    statement = statement.replace('"', "").replace("`", "")
    statement = statement.replace("[", "").replace("]", "")
    statement = re.sub(r"/\*.*?\*/", " ", statement, flags=re.DOTALL)
    statement = re.sub(r"--[^\n\r]*", " ", statement)
    return re.sub(r"\s+", " ", statement).strip()


def _destructive_reason(sql: str) -> Optional[str]:
    if _DROP_CONTAINER_RE.search(sql):
        return "drop schema/database"
    if _DROP_OR_TRUNCATE_RE.search(sql):
        return "drop/truncate on protected account or money table"
    if _DELETE_RE.search(sql):
        return "delete from protected account or money table"
    if _ALTER_DROP_MONEY_RE.search(sql):
        return "drop money column from protected table"

    update_match = _MASS_MONEY_UPDATE_RE.search(sql)
    if update_match is None:
        return None

    set_clause = update_match.group("set_clause")
    where_index = set_clause.lower().find(" where ")
    before_where = set_clause if where_index < 0 else set_clause[:where_index]
    if not _MONEY_FIELD_ASSIGN_RE.search(before_where):
        return None

    if where_index < 0:
        return "mass update of protected money field without account filter"
    if _ZERO_OR_NULL_MONEY_RE.search(before_where):
        return "reset protected money field to zero or null"

    return None


install()
