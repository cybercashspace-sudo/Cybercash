from __future__ import annotations

from collections import defaultdict
from threading import RLock
from typing import Callable, Iterable


class AppEvents:
    WALLET_UPDATED = "WalletUpdated"
    TRANSACTION_CREATED = "TransactionCreated"
    NOTIFICATION_RECEIVED = "NotificationReceived"
    NOTIFICATIONS_UPDATED = "NotificationsUpdated"
    USER_PROFILE_UPDATED = "UserProfileUpdated"
    THEME_CHANGED = "ThemeChanged"
    SESSION_EXPIRED = "SessionExpired"
    CONNECTIVITY_CHANGED = "ConnectivityChanged"


class EventBus:
    """Thread-safe publish/subscribe event bus."""

    def __init__(self):
        self._subscribers: dict[str, list[Callable]] = defaultdict(list)
        self._lock = RLock()

    def subscribe(self, event_name: str, callback: Callable) -> None:
        if not event_name or callback is None:
            return
        with self._lock:
            callbacks = self._subscribers[event_name]
            if callback not in callbacks:
                callbacks.append(callback)

    def unsubscribe(self, event_name: str, callback: Callable) -> None:
        if not event_name or callback is None:
            return
        with self._lock:
            callbacks = self._subscribers.get(event_name, [])
            if callback in callbacks:
                callbacks.remove(callback)
            if not callbacks and event_name in self._subscribers:
                self._subscribers.pop(event_name, None)

    def publish(self, event_name: str, payload=None) -> int:
        with self._lock:
            callbacks = list(self._subscribers.get(event_name, []))

        delivered = 0
        for callback in callbacks:
            try:
                callback(payload)
            except Exception:
                continue
            delivered += 1
        return delivered

    def clear(self, event_names: Iterable[str] | None = None) -> None:
        with self._lock:
            if event_names is None:
                self._subscribers.clear()
                return
            for event_name in event_names:
                self._subscribers.pop(str(event_name or ""), None)

    def listener_count(self, event_name: str) -> int:
        with self._lock:
            return len(self._subscribers.get(event_name, []))
