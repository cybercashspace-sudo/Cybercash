from __future__ import annotations

from requests import HTTPError

from core.dashboard_cache import load_dashboard_cache, save_dashboard_cache
from core.exceptions import NetworkError
from core.message_sanitizer import extract_backend_message
from services.api import FAST_TIMEOUT
from services.base_service import BaseApiService


class NotificationService(BaseApiService):
    def get_notifications(self) -> list[dict]:
        try:
            data = self.get_json("/notifications", timeout=FAST_TIMEOUT)
        except HTTPError as exc:
            message = extract_backend_message(
                getattr(exc.response, "data", None),
                fallback="Unable to load notifications.",
            )
            raise NetworkError(message) from exc
        items = self.extract_items(data, keys=("items", "notifications", "data"))
        save_dashboard_cache(notifications=items)
        return items

    def mark_read(self, notification_id: str) -> dict:
        try:
            data = self.post_json(
                f"/notifications/{notification_id}/read",
                payload={},
                timeout=FAST_TIMEOUT,
            )
        except HTTPError as exc:
            message = extract_backend_message(
                getattr(exc.response, "data", None),
                fallback="Unable to mark notification as read.",
            )
            raise NetworkError(message) from exc
        return data if isinstance(data, dict) else {"status": "ok", "payload": data}

    def load_cached_notifications(self) -> list[dict]:
        cached = load_dashboard_cache()
        if not isinstance(cached, dict):
            return []
        notifications = cached.get("notifications", [])
        return [item for item in notifications if isinstance(item, dict)]
