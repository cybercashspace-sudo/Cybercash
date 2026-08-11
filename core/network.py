from __future__ import annotations

import threading

from api.client import api_client


class NetworkManager:
    """Very small connectivity manager for app-wide reachability checks."""

    def __init__(self):
        self.is_online = True
        self.last_error = ""
        self._lock = threading.RLock()

    def probe(self) -> bool:
        try:
            result = api_client.request("GET", "/health", timeout=(2, 4), failover=False)
            ok = bool(result.get("ok"))
            self._set_state(ok, "" if ok else "Network unavailable")
            return ok
        except Exception as exc:
            self._set_state(False, str(exc) or "Network unavailable")
            return False

    def _set_state(self, online: bool, error: str) -> None:
        with self._lock:
            self.is_online = bool(online)
            self.last_error = str(error or "")

