import os

from kivy.app import App
from kivy.storage.jsonstore import JsonStore

_store = None
_store_path = ""


def _session_store_path() -> str:
    app = App.get_running_app()
    if app is not None:
        user_data_dir = str(getattr(app, "user_data_dir", "") or "").strip()
        if user_data_dir:
            return os.path.join(user_data_dir, "session.json")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "session.json")


def _get_store() -> JsonStore:
    global _store, _store_path
    path = _session_store_path()
    if _store is None or _store_path != path:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        _store = JsonStore(path)
        _store_path = path
    return _store


def save_token(token: str):
    _get_store().put("auth", access_token=str(token or ""))


def get_token() -> str:
    store = _get_store()
    if store.exists("auth"):
        return str(store.get("auth").get("access_token", "") or "")
    return ""
