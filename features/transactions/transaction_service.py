from __future__ import annotations

from services.transaction_service import TransactionService as AppTransactionService


class TransactionService:
    def __init__(self):
        self._service = AppTransactionService()

    def get_transactions(self, *, before_id: int | None = None, limit: int = 100) -> list[dict]:
        return self._service.list_transactions(before_id=before_id, limit=limit)

    def load_cached_transactions(self) -> list[dict]:
        return self._service.load_cached_transactions()

