from __future__ import annotations

from typing import Iterable

try:
    from kivy.utils import platform as kivy_platform
except Exception:
    kivy_platform = ""

try:
    from android.permissions import Permission, request_permissions
except Exception:
    Permission = None
    request_permissions = None


class PermissionManager:
    """Centralizes platform permission requests."""

    def __init__(self):
        self.last_requested: list[str] = []

    @staticmethod
    def _is_android() -> bool:
        return str(kivy_platform or "").strip().lower() == "android"

    def request(self, permissions: Iterable[str]) -> bool:
        requested = [str(permission or "").strip() for permission in permissions if str(permission or "").strip()]
        self.last_requested = requested
        if not requested:
            return True
        if not self._is_android():
            return True
        if request_permissions is None:
            return True
        try:
            request_permissions(requested)
            return True
        except Exception:
            return False

    def request_camera(self) -> bool:
        permission = getattr(Permission, "CAMERA", "android.permission.CAMERA")
        return self.request([permission])

    def request_storage(self) -> bool:
        permissions = []
        read_permission = getattr(Permission, "READ_EXTERNAL_STORAGE", "android.permission.READ_EXTERNAL_STORAGE")
        write_permission = getattr(Permission, "WRITE_EXTERNAL_STORAGE", "android.permission.WRITE_EXTERNAL_STORAGE")
        permissions.extend([read_permission, write_permission])
        media_read_permission = getattr(Permission, "READ_MEDIA_IMAGES", "")
        if media_read_permission:
            permissions.append(media_read_permission)
        return self.request(permissions)

    def request_notifications(self) -> bool:
        permission = getattr(Permission, "POST_NOTIFICATIONS", "android.permission.POST_NOTIFICATIONS")
        return self.request([permission])

    def request_biometrics(self) -> bool:
        permissions = [
            getattr(Permission, "USE_BIOMETRIC", "android.permission.USE_BIOMETRIC"),
            getattr(Permission, "USE_FINGERPRINT", "android.permission.USE_FINGERPRINT"),
        ]
        return self.request(permissions)
