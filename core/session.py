from __future__ import annotations

import time
from dataclasses import dataclass

from storage import token_is_expired

from core.secure_storage import SecureStorage


_storage = SecureStorage()


@dataclass
class SessionSnapshot:
    access_token: str = ""
    refresh_token: str = ""
    expires_at: float | None = None
    remember_me: dict | None = None
    privacy_mode: bool = True
    user: dict | None = None

    @property
    def is_authenticated(self) -> bool:
        token = str(self.access_token or "").strip()
        if not token:
            return False
        if self.expires_at is not None and float(self.expires_at or 0) > 0 and time.time() >= float(self.expires_at):
            return False
        return not token_is_expired(token)


class SessionManager:
    """Owns auth/session persistence for the app."""

    def __init__(self):
        self.token: str = ""
        self.refresh_token: str = ""
        self.expires_at: float | None = None
        self.user: dict | None = None
        self.remember_me: dict | None = None
        self.privacy_mode: bool = True

    @staticmethod
    def _normalize_user(user: dict | None) -> dict | None:
        if not isinstance(user, dict) or not user:
            return None
        return dict(user)

    def restore(self) -> SessionSnapshot:
        self.token = _storage.get_token()
        self.refresh_token = _storage.get_refresh_token()
        self.expires_at = _storage.get_session_expiry()
        self.user = self._normalize_user(_storage.get_user())
        self.remember_me = _storage.get_remember_me()
        self.privacy_mode = bool(_storage.get_privacy_mode())
        return SessionSnapshot(
            access_token=self.token,
            refresh_token=self.refresh_token,
            expires_at=self.expires_at,
            remember_me=self.remember_me,
            privacy_mode=self.privacy_mode,
            user=self.user,
        )

    def save(
        self,
        token: str,
        user: dict | None = None,
        *,
        refresh_token: str | None = None,
        expires_at: float | None = None,
    ) -> None:
        self.token = str(token or "").strip()
        if user is not None:
            self.user = self._normalize_user(user)
        if refresh_token is not None:
            self.refresh_token = str(refresh_token or "").strip()
        if expires_at is not None:
            try:
                self.expires_at = float(expires_at)
            except Exception:
                self.expires_at = None

        _storage.save_token(self.token)
        if refresh_token is not None:
            _storage.save_refresh_token(self.refresh_token)
        if user is not None:
            _storage.save_user(self.user or {})
        if expires_at is not None:
            _storage.save_session_expiry(self.expires_at)

    def start_session(
        self,
        token: str,
        user: dict | None = None,
        *,
        refresh_token: str | None = None,
        expires_at: float | None = None,
    ) -> None:
        self.save(token, user=user, refresh_token=refresh_token, expires_at=expires_at)

    def set_token(self, token: str) -> None:
        self.save(token, refresh_token=self.refresh_token, expires_at=self.expires_at)

    def set_refresh_token(self, refresh_token: str) -> None:
        self.refresh_token = str(refresh_token or "").strip()
        _storage.save_refresh_token(self.refresh_token)

    def set_expiry(self, expires_at: float | None) -> None:
        if expires_at in {None, ""}:
            self.expires_at = None
            _storage.clear_session_expiry()
            return
        try:
            self.expires_at = float(expires_at)
        except Exception:
            self.expires_at = None
        _storage.save_session_expiry(self.expires_at)

    def load(self) -> str:
        return self.restore().access_token

    def authenticated(self) -> bool:
        token = str(self.token or "").strip()
        if not token:
            return False
        if self.expires_at is not None and float(self.expires_at or 0) > 0 and time.time() >= float(self.expires_at):
            return False
        return not token_is_expired(token)

    def clear_auth(self) -> None:
        self.token = ""
        self.refresh_token = ""
        self.expires_at = None
        self.user = None
        _storage.clear_token()
        _storage.clear_refresh_token()
        _storage.clear_user()
        _storage.clear_session_expiry()

    def logout(self) -> None:
        self.clear_auth()

    def clear(self) -> None:
        self.token = ""
        self.refresh_token = ""
        self.expires_at = None
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
        self.user = self._normalize_user(user)
        _storage.save_user(self.user or {})

    def get_user(self) -> dict | None:
        if self.user is not None:
            return self.user
        user = self._normalize_user(_storage.get_user())
        self.user = user
        return user

    def get_remember_me(self) -> dict | None:
        if self.remember_me is not None:
            return self.remember_me
        self.remember_me = _storage.get_remember_me()
        return self.remember_me

    def get_privacy_mode(self) -> bool:
        return self.privacy_mode if self.privacy_mode is not None else _storage.get_privacy_mode()


session = SessionManager()
