from __future__ import annotations

"""Storage abstraction for auth/session data.

This currently delegates to the existing local persistence helpers so the app
keeps working in development builds. The interface is isolated here so Android
secure storage can replace the internals later without changing the rest of the
app.
"""

from storage import (
    clear_remember_me,
    clear_refresh_token,
    clear_session_expiry,
    clear_user,
    clear_token,
    get_privacy_mode,
    get_remember_me,
    get_refresh_token,
    get_session_expiry,
    get_user,
    get_token,
    save_privacy_mode,
    save_remember_me,
    save_refresh_token,
    save_session_expiry,
    save_user,
    save_token,
)


class SecureStorage:
    def save_token(self, token: str) -> None:
        save_token(token)

    def get_token(self) -> str:
        return str(get_token() or "").strip()

    def clear_token(self) -> None:
        clear_token()

    def save_refresh_token(self, refresh_token: str) -> None:
        save_refresh_token(refresh_token)

    def get_refresh_token(self) -> str:
        return str(get_refresh_token() or "").strip()

    def clear_refresh_token(self) -> None:
        clear_refresh_token()

    def save_user(self, user: dict | None) -> None:
        save_user(user)

    def get_user(self) -> dict:
        user = get_user()
        return user if isinstance(user, dict) else {}

    def clear_user(self) -> None:
        clear_user()

    def save_session_expiry(self, expires_at) -> None:
        save_session_expiry(expires_at)

    def get_session_expiry(self):
        return get_session_expiry()

    def clear_session_expiry(self) -> None:
        clear_session_expiry()

    def save_remember_me(self, momo: str, first_name: str = "", pin: str = "") -> None:
        save_remember_me(momo, first_name=first_name, pin=pin)

    def get_remember_me(self) -> dict | None:
        return get_remember_me()

    def clear_remember_me(self) -> None:
        clear_remember_me()

    def save_privacy_mode(self, enabled: bool) -> None:
        save_privacy_mode(bool(enabled))

    def get_privacy_mode(self) -> bool:
        return bool(get_privacy_mode())

    def clear(self) -> None:
        clear_token()
        clear_refresh_token()
        clear_user()
        clear_session_expiry()
        clear_remember_me()
