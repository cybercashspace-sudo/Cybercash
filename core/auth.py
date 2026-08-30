from __future__ import annotations

from api.auth import access_account, lookup_registered_name, logout, register, request_reset_pin_otp, reset_pin, resend_otp, verify_account


class AuthService:
    """Compatibility service wrapper around the existing auth API layer."""

    def login(
        self,
        momo_number: str,
        pin: str,
        is_agent: bool = False,
        first_name: str = "",
        device_id: str = "",
        device_fingerprint: str = "",
    ):
        return access_account(
            momo_number,
            pin,
            is_agent,
            first_name=first_name,
            device_id=device_id,
            device_fingerprint=device_fingerprint,
        )

    def lookup_name(self, momo: str):
        return lookup_registered_name(momo)

    def logout(self, access_token: str):
        return logout(access_token)

    def register(self, *args, **kwargs):
        return register(*args, **kwargs)

    def resend_otp(self, momo: str):
        return resend_otp(momo)

    def verify_account(self, momo: str, otp: str):
        return verify_account(momo, otp)

    def request_reset_pin_otp(self, momo: str):
        return request_reset_pin_otp(momo)

    def reset_pin(self, momo: str, otp: str, new_pin: str):
        return reset_pin(momo, otp, new_pin)
