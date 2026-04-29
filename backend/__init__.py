"""CyberCash backend package."""

from __future__ import annotations

from typing import Any

_LAZY_EXPORTS = {
    "AsyncSessionLocal",
    "Base",
    "SessionLocal",
    "async_engine",
    "async_session",
    "engine",
    "get_db",
}


def __getattr__(name: str) -> Any:
    if name in _LAZY_EXPORTS:
        from .database import AsyncSessionLocal, Base, SessionLocal, async_engine, async_session, engine, get_db

        exports = {
            "AsyncSessionLocal": AsyncSessionLocal,
            "Base": Base,
            "SessionLocal": SessionLocal,
            "async_engine": async_engine,
            "async_session": async_session,
            "engine": engine,
            "get_db": get_db,
        }
        return exports[name]
    raise AttributeError(f"module 'backend' has no attribute {name!r}")

