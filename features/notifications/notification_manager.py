from __future__ import annotations


class NotificationManager:
    def __init__(self):
        self.unread = 0
        self.items: list[dict] = []

    def update(self, notifications):
        items = [item for item in (notifications or []) if isinstance(item, dict)]
        self.items = items
        self.unread = len([item for item in items if not bool(item.get("is_read", False))])

    def append(self, notification: dict):
        if not isinstance(notification, dict):
            return
        self.items.insert(0, notification)
        if not notification.get("is_read", False):
            self.unread += 1

    def clear(self):
        self.unread = 0
        self.items = []


notification_manager = NotificationManager()
