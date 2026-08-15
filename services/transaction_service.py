from __future__ import annotations

from core.dashboard_cache import load_dashboard_cache, save_dashboard_cache
from models.transaction import Transaction
from services.api import api


class TransactionService:
    @staticmethod
    def _extract_items(payload) -> list[dict]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            for key in ("items", "results", "transactions", "data"):
                value = payload.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
        return []

    def get_transactions(self, page: int = 1, limit: int = 20):
        last_error = None
        for path, params in (
            ("/transactions", {"page": page, "limit": limit}),
            ("/transactions/recent", {"page": page, "limit": limit}),
            ("/wallet/transactions/me", {"page": page, "limit": limit}),
        ):
            try:
                response = api.get(path, params=params)
                response.raise_for_status()
                payload = response.json()
                items = self._extract_items(payload)
                if items:
                    save_dashboard_cache(transactions=items)
                return payload
            except Exception as exc:
                last_error = exc
                continue
        if last_error is not None:
            raise last_error
        return []

    def list_transactions(self, page: int = 1, limit: int = 20) -> list[dict]:
        payload = self.get_transactions(page=page, limit=limit)
        return self._extract_items(payload)

    def get_transaction_models(self, page: int = 1, limit: int = 20) -> list[Transaction]:
        return [Transaction.from_payload(item) for item in self.list_transactions(page=page, limit=limit)]

    def load_cached_transactions(self) -> list[dict]:
        cached = load_dashboard_cache()
        if not isinstance(cached, dict):
            return []
        transactions = cached.get("transactions", [])
        return [item for item in transactions if isinstance(item, dict)]
