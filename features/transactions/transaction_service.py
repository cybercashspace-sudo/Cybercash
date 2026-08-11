from __future__ import annotations

from api.client import FAST_TIMEOUT, api_client
from core.dashboard_cache import load_dashboard_cache, save_dashboard_cache
from core.exceptions import NetworkError


class TransactionService:
    def get_transactions(self, page: int = 1, limit: int = 20) -> list[dict]:
        for path, params in (
            ("/transactions", {"page": page, "limit": limit}),
            ("/transactions/recent", {"page": page, "limit": limit}),
            ("/wallet/transactions/me", {"page": page, "limit": limit}),
        ):
            result = api_client.request("GET", path, params=params, timeout=FAST_TIMEOUT)
            status_code = int(result.get("status_code", 0) or 0)
            data = result.get("data", {})
            if status_code >= 400:
                continue
            if isinstance(data, list):
                items = [item for item in data if isinstance(item, dict)]
            elif isinstance(data, dict):
                items = [item for item in data.get("items", []) if isinstance(item, dict)]
                if not items:
                    items = [item for item in data.get("transactions", []) if isinstance(item, dict)]
            else:
                items = []
            save_dashboard_cache(transactions=items)
            return items
        return []

    def load_cached_transactions(self) -> list[dict]:
        cached = load_dashboard_cache()
        if not isinstance(cached, dict):
            return []
        return [item for item in cached.get("transactions", []) if isinstance(item, dict)]
