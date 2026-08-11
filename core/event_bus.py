from __future__ import annotations

from collections import defaultdict
from typing import Callable


class EventBus:
    """Lightweight publish/subscribe event bus."""

    def __init__(self):
        self._subscribers: dict[str, list[Callable]] = defaultdict(list)

    def subscribe(self, event_name: str, callback: Callable) -> None:
        if callback not in self._subscribers[event_name]:
            self._subscribers[event_name].append(callback)

    def unsubscribe(self, event_name: str, callback: Callable) -> None:
        callbacks = self._subscribers.get(event_name, [])
        if callback in callbacks:
            callbacks.remove(callback)

    def publish(self, event_name: str, payload=None) -> None:
        for callback in list(self._subscribers.get(event_name, [])):
            try:
                callback(payload)
            except Exception:
                continue

