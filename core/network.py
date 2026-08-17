from __future__ import annotations

import time
from threading import RLock
from typing import Callable

from api.client import api_client

from core.event_bus import AppEvents
from core.message_sanitizer import extract_backend_message


class NetworkManager:
    """Centralized connectivity manager for the app."""

    def __init__(self, client=None, event_bus=None):
        self.client = client or api_client
        self.event_bus = event_bus
        self.is_online = True
        self.last_error = ""
        self.last_checked_at = 0.0
        self._lock = RLock()
        self._listeners: list[Callable[[dict], None]] = []

    def bind(self, callback: Callable[[dict], None]) -> None:
        if callback is None:
            return
        with self._lock:
            if callback not in self._listeners:
                self._listeners.append(callback)

    def unbind(self, callback: Callable[[dict], None]) -> None:
        if callback is None:
            return
        with self._lock:
            if callback in self._listeners:
                self._listeners.remove(callback)

    def set_event_bus(self, event_bus) -> None:
        self.event_bus = event_bus

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "online": bool(self.is_online),
                "error": str(self.last_error or ""),
                "last_checked_at": float(self.last_checked_at or 0.0),
            }

    def can_request(self) -> bool:
        return bool(self.is_online)

    def probe(self, path: str = "/health") -> bool:
        try:
            result = self.client.request("GET", path, timeout=(2, 4), failover=False)
            ok = bool(result.get("ok"))
            data = result.get("data", {}) if isinstance(result, dict) else {}
            error = "" if ok else extract_backend_message(data, fallback="Network unavailable")
            self._set_state(ok, error)
            return ok
        except Exception as exc:
            self._set_state(False, extract_backend_message(str(exc), fallback="Network unavailable"))
            return False

    def refresh(self, path: str = "/health") -> bool:
        return self.probe(path=path)

    def _set_state(self, online: bool, error: str) -> None:
        with self._lock:
            changed = bool(self.is_online) != bool(online) or str(self.last_error or "") != str(error or "")
            self.is_online = bool(online)
            self.last_error = str(error or "")
            self.last_checked_at = time.time()

        if changed:
            self._notify_listeners()

    def _notify_listeners(self) -> None:
        snapshot = self.snapshot()
        with self._lock:
            listeners = list(self._listeners)
        for callback in listeners:
            try:
                callback(snapshot)
            except Exception:
                continue
        if self.event_bus is not None:
            try:
                self.event_bus.publish(AppEvents.CONNECTIVITY_CHANGED, snapshot)
            except Exception:
                pass
