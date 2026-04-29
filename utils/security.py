import bcrypt
from werkzeug.security import check_password_hash


def hash_pin(pin: str) -> str:
    raw_pin = str(pin or "").strip()
    if not raw_pin:
        raise ValueError("PIN is required")
    return bcrypt.hashpw(raw_pin.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_pin(pin: str, hashed: str | None) -> bool:
    raw_pin = str(pin or "").strip()
    hashed_value = str(hashed or "").strip()
    if not raw_pin or not hashed_value:
        return False

    # Legacy hashes may use werkzeug format (e.g. pbkdf2:...).
    if ":" in hashed_value and not hashed_value.startswith("$2"):
        try:
            return bool(check_password_hash(hashed_value, raw_pin))
        except Exception:
            return False

    try:
        return bool(bcrypt.checkpw(raw_pin.encode("utf-8"), hashed_value.encode("utf-8")))
    except Exception:
        return False
