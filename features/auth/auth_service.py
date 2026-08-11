from __future__ import annotations

from core.auth import AuthService as CoreAuthService


class AuthService:
    """Thin auth service wrapper for feature modules."""

    def __init__(self):
        self._backend = CoreAuthService()

    def login(
        self,
        identifier: str,
        password: str,
        is_agent: bool = False,
        first_name: str = "",
        device_id: str = "",
        device_fingerprint: str = "",
    ):
        return self._backend.login(
            identifier,
            password,
            bool(is_agent),
            first_name=first_name,
            device_id=device_id,
            device_fingerprint=device_fingerprint,
        )

    def register(self, payload: dict):
        return self._backend.register(payload)

    def lookup_name(self, identifier: str):
        return self._backend.lookup_name(identifier)

    def resend_otp(self, momo: str):
        return self._backend.resend_otp(momo)

    def verify_account(self, momo: str, otp: str):
        return self._backend.verify_account(momo, otp)

    def request_reset_pin_otp(self, momo: str):
        return self._backend.request_reset_pin_otp(momo)

    def reset_pin(self, momo: str, otp: str, new_pin: str):
        return self._backend.reset_pin(momo, otp, new_pin)

    def logout(self, access_token: str):
        return self._backend.logout(access_token)
