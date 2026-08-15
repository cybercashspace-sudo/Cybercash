from __future__ import annotations

from core.dashboard_cache import load_dashboard_cache, save_dashboard_cache
from services.api import FAST_TIMEOUT, api
from services.transaction_service import TransactionService as AppTransactionService
from services.wallet_service import WalletService


class HomeService:
    def __init__(self):
        self.wallet_service = WalletService()
        self.transaction_service = AppTransactionService()

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

    def _request_json(self, path: str, params: dict | None = None):
        response = api.get(path, params=params, timeout=FAST_TIMEOUT)
        response.raise_for_status()
        return response.json()

    def get_wallet(self) -> dict:
        try:
            payload = self.wallet_service.get_wallet()
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}

    def get_transactions(self, limit: int = 10) -> list[dict]:
        try:
            return self.transaction_service.list_transactions(limit=limit)
        except Exception:
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

