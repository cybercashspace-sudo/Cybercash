from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from kivy.app import App


_CACHE_DIR_NAME = "dashboard_cache"


def _cache_dir() -> Path:
    app = App.get_running_app()
    base_dir: Path
    if app is not None:
        user_data_dir = str(getattr(app, "user_data_dir", "") or "").strip()
        base_dir = Path(user_data_dir) if user_data_dir else Path(__file__).resolve().parents[1]
    else:
        base_dir = Path(__file__).resolve().parents[1]
    cache_dir = base_dir / _CACHE_DIR_NAME
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def _cache_file(name: str) -> Path:
    return _cache_dir() / f"{name}.json"


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_json(path: Path, payload: Any) -> None:
    try:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def load_dashboard_cache() -> dict[str, Any]:
    """Load cached dashboard payloads if available."""

    return {
        "profile": _read_json(_cache_file("profile")) or {},
        "wallet": _read_json(_cache_file("wallet")) or {},
        "transactions": _read_json(_cache_file("transactions")) or [],
        "notifications": _read_json(_cache_file("notifications")) or [],
    }


def save_dashboard_cache(*, profile=None, wallet=None, transactions=None, notifications=None) -> None:
    """Persist the latest dashboard snapshot for fast cold-starts."""

    if profile is not None:
        _write_json(_cache_file("profile"), profile)
    if wallet is not None:
        _write_json(_cache_file("wallet"), wallet)
    if transactions is not None:
        _write_json(_cache_file("transactions"), transactions)
    if notifications is not None:
        _write_json(_cache_file("notifications"), notifications)

