from __future__ import annotations

from services.transaction_service import TransactionService as AppTransactionService


class TransactionService:
    def __init__(self):
        self._service = AppTransactionService()

    def get_transactions(self, page: int = 1, limit: int = 20) -> list[dict]:
        return self._service.list_transactions(page=page, limit=limit)

    def load_cached_transactions(self) -> list[dict]:
        return self._service.load_cached_transactions()

