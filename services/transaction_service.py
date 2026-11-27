from __future__ import annotations

from models.transaction import Transaction
from services.base_service import BaseApiService


class TransactionService(BaseApiService):
    def get_transactions(self, *, before_id: int | None = None, limit: int = 100):
        params = {"limit": max(1, min(int(limit or 100), 500))}
        if before_id is not None:
            params["before_id"] = max(1, int(before_id))
        return self.get_json("/wallet/transactions/me", params=params)

    def list_transactions(self, *, before_id: int | None = None, limit: int = 100) -> list[dict]:
        payload = self.get_transactions(before_id=before_id, limit=limit)
        return self.extract_items(payload)

    def get_transaction_models(self, *, before_id: int | None = None, limit: int = 100) -> list[Transaction]:
        return [Transaction.from_payload(item) for item in self.list_transactions(before_id=before_id, limit=limit)]

    def load_cached_transactions(self) -> list[dict]:
        # Transaction history contains personal data. Do not read from the
        # shared dashboard cache, which is not scoped to the signed-in user.
        return []
