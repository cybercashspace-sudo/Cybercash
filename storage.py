import os
import base64
import json
import time
from kivy.utils import platform

from kivy.app import App
from kivy.storage.jsonstore import JsonStore

_store = None
_store_path = ""
TOKEN_EXPIRY_SKEW_SECONDS = 30


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
    try:
        _get_store().put("auth", access_token=str(token or ""))
    except Exception:
        return


def clear_token():
    save_token("")


def save_privacy_mode(enabled: bool):
    try:
        _get_store().put("settings", privacy_mode=bool(enabled))
    except Exception:
        pass


def get_privacy_mode() -> bool:
    try:
        store = _get_store()
        if store.exists("settings"):
            return bool(store.get("settings").get("privacy_mode", True))
    except Exception:
        return True
    return True


def _decode_jwt_payload(token: str) -> dict:
    try:
        payload_part = str(token or "").split(".")[1]
        padded = payload_part + ("=" * (-len(payload_part) % 4))
        decoded = base64.urlsafe_b64decode(padded.encode("ascii"))
        payload = json.loads(decoded.decode("utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def token_is_expired(token: str) -> bool:
    payload = _decode_jwt_payload(token)
    exp = payload.get("exp")
    if exp in {None, ""}:
        return False
    try:
        return float(exp) <= (time.time() + TOKEN_EXPIRY_SKEW_SECONDS)
    except Exception:
        return False


def get_token() -> str:
    try:
        store = _get_store()
        if store.exists("auth"):
            token = str(store.get("auth").get("access_token", "") or "").strip()
            if token and token_is_expired(token):
                clear_token()
                return ""
            return token
    except Exception:
        return ""
    return ""
