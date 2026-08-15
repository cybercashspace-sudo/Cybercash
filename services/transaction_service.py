from __future__ import annotations

from features.transactions.transaction_service import TransactionService as _TransactionService
from models.transaction import Transaction


class TransactionService(_TransactionService):
    """App-facing transaction facade."""

    def get_transaction_models(self, page: int = 1, limit: int = 20) -> list[Transaction]:
        return [Transaction.from_payload(item) for item in self.get_transactions(page=page, limit=limit)]

    def load_cached_transaction_models(self) -> list[Transaction]:
        return [Transaction.from_payload(item) for item in self.load_cached_transactions()]


__all__ = ["TransactionService"]
