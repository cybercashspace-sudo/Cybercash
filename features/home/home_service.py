from __future__ import annotations

from core.dashboard_cache import load_dashboard_cache, save_dashboard_cache
from services.base_service import BaseApiService
from services.transaction_service import TransactionService as AppTransactionService
from services.wallet_service import WalletService


class HomeService(BaseApiService):
    def __init__(self):
        self.wallet_service = WalletService()
        self.transaction_service = AppTransactionService()

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
                payload = self.get_json(path, params=params)
                rows = self.extract_items(payload)
                if rows:
                    return rows
            except Exception:
                continue
        return []

    def get_profile(self) -> dict:
        for path in ("/users/me", "/auth/me"):
            try:
                payload = self.get_json(path)
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
