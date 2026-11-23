import json
import logging
import os

from kivy.app import App
from kivy.storage.jsonstore import JsonStore

logger = logging.getLogger(__name__)
_store = None
_store_path = ""


def _session_store_path() -> str:
    app = App.get_running_app()
    if app is not None:
        user_data_dir = str(getattr(app, "user_data_dir", "") or "").strip()
        if user_data_dir:
            return os.path.join(user_data_dir, "session.json")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "session.json")


def _validate_session_file(path: str) -> None:
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("session data must be a JSON object")
    auth = payload.get("auth")
    if auth is not None and not isinstance(auth, dict):
        raise ValueError("session auth data must be a JSON object")


def _get_store() -> JsonStore | None:
    global _store, _store_path
    path = _session_store_path()
    if _store is not None and _store_path == path:
        return _store

    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            _validate_session_file(path)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
            # A broken saved token should sign the user out cleanly, not crash app startup.
            try:
                os.remove(path)
            except FileNotFoundError:
                pass
            except OSError:
                logger.warning("Saved session is unreadable; continuing signed out.")
                _store = None
                _store_path = path
                return None
            logger.warning("Saved session was unreadable and has been cleared.")

        _store = JsonStore(path)
        _store_path = path
        return _store
    except Exception as exc:
        logger.warning("Unable to open saved session (%s); continuing signed out.", type(exc).__name__)
        _store = None
        _store_path = path
        return None


def save_token(token: str) -> bool:
    store = _get_store()
    if store is None:
        return False
    try:
        store.put("auth", access_token=str(token or ""))
        return True
    except Exception as exc:
        logger.warning("Unable to save session (%s).", type(exc).__name__)
        return False


def get_token() -> str:
    store = _get_store()
    if store is None:
        return ""
    try:
        if not store.exists("auth"):
            return ""
        record = store.get("auth")
        if not isinstance(record, dict):
            return ""
        token = record.get("access_token", "")
        return token.strip() if isinstance(token, str) else ""
    except Exception as exc:
        logger.warning("Unable to read saved session (%s); continuing signed out.", type(exc).__name__)
        return ""