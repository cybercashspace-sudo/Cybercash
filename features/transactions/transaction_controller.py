from __future__ import annotations

from features.transactions.filters import filter_transactions
from features.transactions.transaction_service import TransactionService


class TransactionController:
    def __init__(self, service: TransactionService | None = None):
        self.service = service or TransactionService()

    def load_transactions(self, page: int = 1, limit: int = 20) -> list[dict]:
        rows = self.service.get_transactions(page=page, limit=limit)
        return [self.normalize(item) for item in rows]

    def load_cached_transactions(self) -> list[dict]:
        rows = self.service.load_cached_transactions()
        return [self.normalize(item) for item in rows]

    def apply_filters(self, rows, tx_type: str = "all", query: str = ""):
        return filter_transactions(rows, tx_type=tx_type, query=query)

    @staticmethod
    def normalize(item: dict) -> dict:
        payload = dict(item or {})
        amount = payload.get("amount", 0)
        try:
            amount_value = float(amount)
        except Exception:
            amount_value = 0.0
        amount_text = f"{amount_value:,.2f}"
        if amount_value >= 0:
            amount_text = f"+ GH₵ {amount_text}"
        else:
            amount_text = f"- GH₵ {abs(amount_value):,.2f}"
        return {
            "transaction_id": str(payload.get("id") or payload.get("transaction_id") or ""),
            "type": str(payload.get("type") or payload.get("transaction_type") or "Transaction"),
            "amount": amount_value,
            "amount_text": amount_text,
            "status": str(payload.get("status") or ""),
            "status_text": str(payload.get("status") or ""),
            "created_at": str(payload.get("created_at") or payload.get("date") or ""),
            "date_text": str(payload.get("created_at") or payload.get("date") or ""),
            "description": str(payload.get("description") or ""),
            "reference": str(payload.get("reference") or ""),
            "is_read": bool(payload.get("is_read", True)),
            "raw": payload,
        }
