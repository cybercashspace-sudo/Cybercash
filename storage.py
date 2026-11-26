import os
import base64
import json
import hashlib
import time
from kivy.app import App

try:
    from cryptography.fernet import Fernet
except Exception:
    Fernet = None

TOKEN_EXPIRY_SKEW_SECONDS = 30
KEY_FILE = ".storage.key"

def _session_store_path() -> str:
    app = App.get_running_app()
    if app is not None:
        user_data_dir = str(getattr(app, "user_data_dir", "") or "").strip()
        if user_data_dir:
            return os.path.join(user_data_dir, "session.json")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "session.json")


def _get_encryption_key() -> bytes:
    if Fernet is None:
        return b""

    path = _session_store_path()
    key_path = os.path.join(os.path.dirname(path), KEY_FILE)
    
    if os.path.exists(key_path):
        with open(key_path, "rb") as f:
            return f.read()
    
    # Generate a new key if none exists
    new_key = Fernet.generate_key()
    os.makedirs(os.path.dirname(key_path), exist_ok=True)
    with open(key_path, "wb") as f:
        f.write(new_key)
    return new_key


def _read_plain_data() -> dict:
    path = _session_store_path()
    if not os.path.exists(path):
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _write_plain_data(data: dict):
    path = _session_store_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)

    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception:
        pass


def _read_secure_data() -> dict:
    if Fernet is None:
        return _read_plain_data()

    path = _session_store_path()
    if not os.path.exists(path):
        return {}
    
    try:
        fernet = Fernet(_get_encryption_key())
        with open(path, "rb") as f:
            encrypted_data = f.read()
        decrypted_data = fernet.decrypt(encrypted_data)
        payload = json.loads(decrypted_data.decode("utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return _read_plain_data()


def _write_secure_data(data: dict):
    if Fernet is None:
        _write_plain_data(data)
        return

    path = _session_store_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    
    try:
        fernet = Fernet(_get_encryption_key())
        json_str = json.dumps(data)
        encrypted_data = fernet.encrypt(json_str.encode("utf-8"))
        with open(path, "wb") as f:
            f.write(encrypted_data)
    except Exception:
        pass


def save_token(token: str):
    try:
        data = _read_secure_data()
        data["access_token"] = str(token or "")
        _write_secure_data(data)
    except Exception:
        return


def clear_token():
    save_token("")


def save_refresh_token(refresh_token: str):
    try:
        data = _read_secure_data()
        data["refresh_token"] = str(refresh_token or "")
        _write_secure_data(data)
    except Exception:
        return


def get_refresh_token() -> str:
    try:
        data = _read_secure_data()
        return str(data.get("refresh_token", "") or "").strip()
    except Exception:
        return ""


def clear_refresh_token():
    save_refresh_token("")


def save_user(user: dict | None):
    try:
        data = _read_secure_data()
        data["user"] = user if isinstance(user, dict) else {}
        _write_secure_data(data)
    except Exception:
        pass


def get_user() -> dict:
    data = _read_secure_data()
    user = data.get("user", {})
    return user if isinstance(user, dict) else {}


def clear_user():
    save_user({})


def save_session_expiry(expires_at):
    try:
        data = _read_secure_data()
        if expires_at in {None, ""}:
            data.pop("expires_at", None)
        else:
            data["expires_at"] = float(expires_at)
        _write_secure_data(data)
    except Exception:
        pass


def get_session_expiry():
    data = _read_secure_data()
    expires_at = data.get("expires_at")
    if expires_at in {None, ""}:
        return None
    try:
        return float(expires_at)
    except Exception:
        return None


def clear_session_expiry():
    save_session_expiry(None)


def save_remember_me(momo: str, first_name: str = ""):
    try:
        data = _read_secure_data()
        data["remember_me"] = {
            "momo": str(momo or "").strip(),
            "first_name": str(first_name or "").strip(),
        }
        # Remove credentials left by older versions.
        data.pop("pin", None)
        data["remember_me"].pop("biometric_enabled", None)
        _write_secure_data(data)
    except Exception:
        pass


def get_remember_me() -> dict:
    data = _read_secure_data()
    remembered = data.get("remember_me", {})
    if not isinstance(remembered, dict):
        remembered = {}

    # Preserve compatibility with older session files that used top-level keys.
    legacy = {
        "momo": data.get("momo", ""),
        "first_name": data.get("first_name", ""),
    }
    result = {
        "momo": str(remembered.get("momo", legacy["momo"]) or "").strip(),
        "first_name": str(remembered.get("first_name", legacy["first_name"]) or "").strip(),
    }
    if "pin" in remembered or "pin" in data or "biometric_enabled" in remembered:
        remembered.pop("pin", None)
        remembered.pop("biometric_enabled", None)
        data.pop("pin", None)
        if isinstance(data.get("remember_me"), dict):
            data["remember_me"] = remembered
        _write_secure_data(data)
    return result


def clear_remember_me():
    try:
        data = _read_secure_data()
        data.pop("remember_me", None)
        data.pop("momo", None)
        data.pop("first_name", None)
        data.pop("pin", None)
        _write_secure_data(data)
    except Exception:
        pass


def save_privacy_mode(enabled: bool):
    try:
        data = _read_secure_data()
        data["privacy_mode"] = bool(enabled)
        _write_secure_data(data)
    except Exception:
        pass


def get_privacy_mode() -> bool:
    data = _read_secure_data()
    return bool(data.get("privacy_mode", True))


def save_loan_terms_acceptance(user_key: str, version: str) -> None:
    """Persist a versioned loan terms acceptance without storing account identifiers."""
    normalized_user = str(user_key or "").strip().lower()
    normalized_version = str(version or "").strip()
    if not normalized_user or not normalized_version:
        return
    try:
        data = _read_secure_data()
        acceptances = data.get("loan_terms_acceptance")
        if not isinstance(acceptances, dict):
            acceptances = {}
        user_hash = hashlib.sha256(normalized_user.encode("utf-8")).hexdigest()
        acceptances[user_hash] = {
            "version": normalized_version,
            "accepted_at": time.time(),
        }
        data["loan_terms_acceptance"] = acceptances
        _write_secure_data(data)
    except Exception:
        return


def get_loan_terms_acceptance(user_key: str) -> str:
    normalized_user = str(user_key or "").strip().lower()
    if not normalized_user:
        return ""
    try:
        data = _read_secure_data()
        acceptances = data.get("loan_terms_acceptance")
        if not isinstance(acceptances, dict):
            return ""
        user_hash = hashlib.sha256(normalized_user.encode("utf-8")).hexdigest()
        value = acceptances.get(user_hash)
        if isinstance(value, dict):
            return str(value.get("version") or "").strip()
        return str(value or "").strip()
    except Exception:
        return ""


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
        data = _read_secure_data()
        token = str(data.get("access_token", "") or "").strip()
        if token and token_is_expired(token):
            clear_token()
            return ""
        return token
    except Exception:
        return ""
    return ""
