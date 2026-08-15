from __future__ import annotations

from dataclasses import dataclass

from core.secure_storage import SecureStorage


_storage = SecureStorage()


@dataclass
class SessionSnapshot:
    access_token: str = ""
    remember_me: dict | None = None
    privacy_mode: bool = True
    user: dict | None = None


class SessionManager:
    """Owns auth/session persistence."""

    def __init__(self):
        self.token: str = ""
        self.user: dict | None = None
        self.remember_me: dict | None = None
        self.privacy_mode: bool = True

    def restore(self) -> SessionSnapshot:
        self.token = _storage.get_token()
        self.remember_me = _storage.get_remember_me()
        self.privacy_mode = bool(_storage.get_privacy_mode())
        return SessionSnapshot(
            access_token=self.token,
            remember_me=self.remember_me,
            privacy_mode=self.privacy_mode,
            user=self.user,
        )

    def set_token(self, token: str) -> None:
        self.save(token)

    def load(self) -> str:
        return self.restore().access_token

    def save(self, token: str, user: dict | None = None) -> None:
        self.token = str(token or "").strip()
        self.user = user or self.user
        _storage.save_token(self.token)

    def authenticated(self) -> bool:
        return bool(str(self.token or "").strip())

    def clear(self) -> None:
        self.token = ""
        self.user = None
        self.remember_me = None
        self.privacy_mode = True
        _storage.clear()

    def set_remember_me(self, momo: str, first_name: str = "", pin: str = "") -> None:
        self.remember_me = {"momo": momo, "first_name": first_name, "pin": pin}
        _storage.save_remember_me(momo, first_name=first_name, pin=pin)

    def clear_remember_me(self) -> None:
        self.remember_me = None
        _storage.clear_remember_me()

    def set_privacy_mode(self, enabled: bool) -> None:
        self.privacy_mode = bool(enabled)
        _storage.save_privacy_mode(self.privacy_mode)

    def set_user(self, user: dict | None) -> None:
        self.user = user

    def get_user(self) -> dict | None:
        return self.user

    def get_remember_me(self) -> dict | None:
        if self.remember_me is not None:
            return self.remember_me
        self.remember_me = _storage.get_remember_me()
        return self.remember_me

    def get_privacy_mode(self) -> bool:
        return self.privacy_mode if self.privacy_mode is not None else _storage.get_privacy_mode()


session = SessionManager()
