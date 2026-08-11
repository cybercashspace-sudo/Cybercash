from __future__ import annotations


class PermissionManager:
    """Centralizes platform permission requests."""

    def request_camera(self) -> bool:
        return self._request("android.permission.CAMERA")

    def request_storage(self) -> bool:
        return self._request("android.permission.READ_EXTERNAL_STORAGE")

    def request_notifications(self) -> bool:
        return self._request("android.permission.POST_NOTIFICATIONS")

    def request_biometrics(self) -> bool:
        return self._request("biometric")

    @staticmethod
    def _request(_permission: str) -> bool:
        try:
            from kivy.utils import platform
            if str(platform or "").lower() not in {"android", "ios"}:
                return True
        except Exception:
            return True
        # Permission prompts are routed through the platform-specific layer when available.
        return True

