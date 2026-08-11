from __future__ import annotations

from features.notifications.notification_manager import notification_manager
from features.notifications.notification_service import NotificationService


class NotificationController:
    def __init__(self, service: NotificationService | None = None):
        self.service = service or NotificationService()

    def load_notifications(self) -> list[dict]:
        items = self.service.get_notifications()
        notification_manager.update(items)
        return items

    def load_cached_notifications(self) -> list[dict]:
        items = self.service.load_cached_notifications()
        notification_manager.update(items)
        return items

    def mark_read(self, notification_id: str):
        result = self.service.mark_read(notification_id)
        for item in notification_manager.items:
            if str(item.get("id") or "") == str(notification_id or ""):
                item["is_read"] = True
        notification_manager.update(notification_manager.items)
        return result
