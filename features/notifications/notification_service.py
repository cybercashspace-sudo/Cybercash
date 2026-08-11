from __future__ import annotations

from api.client import FAST_TIMEOUT, api_client
from core.dashboard_cache import load_dashboard_cache, save_dashboard_cache
from core.exceptions import NetworkError


class NotificationService:
    def get_notifications(self) -> list[dict]:
        result = api_client.request("GET", "/notifications", timeout=FAST_TIMEOUT)
        status_code = int(result.get("status_code", 0) or 0)
        data = result.get("data", {})
        if status_code >= 400:
            message = ""
            if isinstance(data, dict):
                message = str(data.get("detail") or data.get("message") or "").strip()
            raise NetworkError(message or "Unable to load notifications.")
        if isinstance(data, list):
            items = [item for item in data if isinstance(item, dict)]
        elif isinstance(data, dict):
            items = [item for item in data.get("items", []) if isinstance(item, dict)]
            if not items:
                items = [item for item in data.get("notifications", []) if isinstance(item, dict)]
        else:
            items = []
        save_dashboard_cache(notifications=items)
        return items

    def mark_read(self, notification_id: str) -> dict:
        result = api_client.request(
            "POST",
            f"/notifications/{notification_id}/read",
            payload={},
            timeout=FAST_TIMEOUT,
        )
        status_code = int(result.get("status_code", 0) or 0)
        data = result.get("data", {})
        if status_code >= 400:
            message = ""
            if isinstance(data, dict):
                message = str(data.get("detail") or data.get("message") or "").strip()
            raise NetworkError(message or "Unable to mark notification as read.")
        return data if isinstance(data, dict) else {"status": "ok", "payload": data}

    def load_cached_notifications(self) -> list[dict]:
        cached = load_dashboard_cache()
        if not isinstance(cached, dict):
            return []
        notifications = cached.get("notifications", [])
        return [item for item in notifications if isinstance(item, dict)]
