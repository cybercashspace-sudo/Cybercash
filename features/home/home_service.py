from __future__ import annotations

from api.client import FAST_TIMEOUT, api_client
from core.dashboard_cache import load_dashboard_cache, save_dashboard_cache
from core.exceptions import NetworkError


class HomeService:
    def _request_json(self, path: str, params: dict | None = None):
        result = api_client.get(path, params=params, timeout=FAST_TIMEOUT)
        status_code = int(result.get("status_code", 0) or 0)
        data = result.get("data")
        if status_code < 400:
            return data
        message = ""
        if isinstance(data, dict):
            message = str(data.get("detail") or data.get("message") or "").strip()
        if not message:
            message = f"Request to {path} failed with HTTP {status_code}"
        raise NetworkError(message)

    @staticmethod
    def _as_list(payload) -> list[dict]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            for key in ("items", "results", "transactions", "notifications", "data"):
                value = payload.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
        return []

    def get_wallet(self) -> dict:
        for path in ("/wallet/me", "/api/wallet/me"):
            try:
                payload = self._request_json(path)
                if isinstance(payload, dict):
                    return payload
            except Exception:
                continue
        return {}

    def get_transactions(self, limit: int = 10) -> list[dict]:
        for path, params in (
            ("/transactions/recent", {"limit": limit}),
            ("/transactions", {"limit": limit}),
            ("/wallet/transactions/me", {"limit": limit}),
        ):
            try:
                payload = self._request_json(path, params=params)
                rows = self._as_list(payload)
                if rows:
                    return rows
            except Exception:
                continue
        return []

    def get_notifications(self, limit: int = 10) -> list[dict]:
        for path, params in (
            ("/notifications", {"limit": limit}),
            ("/notifications/recent", {"limit": limit}),
        ):
            try:
                payload = self._request_json(path, params=params)
                rows = self._as_list(payload)
                if rows:
                    return rows
            except Exception:
                continue
        return []

    def get_profile(self) -> dict:
        for path in ("/users/me", "/auth/me"):
            try:
                payload = self._request_json(path)
                if isinstance(payload, dict):
                    return payload
            except Exception:
                continue
        return {}

    def get_dashboard(self) -> dict:
        profile = self.get_profile()
        wallet = self.get_wallet()
        transactions = self.get_transactions()
        notifications = self.get_notifications()
        payload = {
            "profile": profile,
            "wallet": wallet,
            "transactions": transactions,
            "notifications": notifications,
            "source": "network",
        }
        save_dashboard_cache(
            profile=profile,
            wallet=wallet,
            transactions=transactions,
            notifications=notifications,
        )
        return payload

    def load_cached_dashboard(self) -> dict:
        data = load_dashboard_cache()
        if not isinstance(data, dict):
            return {}
        return data
