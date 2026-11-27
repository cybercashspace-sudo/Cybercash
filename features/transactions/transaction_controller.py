from __future__ import annotations

import json

from features.transactions.filters import filter_transactions
from features.transactions.transaction_service import TransactionService


class TransactionController:
    def __init__(self, service: TransactionService | None = None):
        self.service = service or TransactionService()

    def load_transactions(self, *, before_id: int | None = None, limit: int = 100) -> list[dict]:
        rows = self.service.get_transactions(before_id=before_id, limit=limit)
        return [self.normalize(item) for item in rows]

    def load_cached_transactions(self) -> list[dict]:
        rows = self.service.load_cached_transactions()
        return [self.normalize(item) for item in rows]

    def apply_filters(self, rows, tx_type: str = "all", query: str = ""):
        return filter_transactions(rows, tx_type=tx_type, query=query)

    @staticmethod
    def normalize(item: dict) -> dict:
        payload = dict(item or {})
        metadata = payload.get("metadata_json")
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except (TypeError, ValueError):
                metadata = {}
        if not isinstance(metadata, dict):
            metadata = {}

        try:
            amount_value = float(payload.get("amount", 0) or 0)
        except (TypeError, ValueError):
            amount_value = 0.0

        direction = str(payload.get("direction") or payload.get("entry_type") or "").strip().lower()
        if amount_value > 0 and direction in {"debit", "out", "outgoing", "sent", "withdrawal"}:
            amount_value = -abs(amount_value)

        timestamp = str(
            payload.get("timestamp") or payload.get("created_at") or payload.get("date") or ""
        ).strip()
        reference = str(
            payload.get("reference")
            or payload.get("provider_reference")
            or metadata.get("reference")
            or metadata.get("provider_reference")
            or metadata.get("payment_reference")
            or ""
        ).strip()
        return {
            "transaction_id": str(payload.get("id") or payload.get("transaction_id") or "").strip(),
            "type": str(payload.get("type") or payload.get("transaction_type") or "Transaction").strip(),
            "amount": amount_value,
            "amount_text": f"{'+' if amount_value >= 0 else '-'} GH\u20b5 {abs(amount_value):,.2f}",
            "currency": str(payload.get("currency") or "GHS").strip(),
            "direction": direction,
            "status": str(payload.get("status") or "Unknown").strip(),
            "status_text": str(payload.get("status") or "Unknown").strip(),
            "created_at": timestamp,
            "date_text": timestamp,
            "description": str(payload.get("description") or "").strip(),
            "reference": reference,
            "username": str(payload.get("username") or payload.get("full_name") or "").strip(),
            "momo_number": str(payload.get("momo_number") or payload.get("phone_number") or "").strip(),
            "is_read": bool(payload.get("is_read", True)),
        }

    @staticmethod
    def merge_transactions(existing, incoming) -> list[dict]:
        """Merge newest-first pages by stable transaction ID without dropping history."""
        merged: list[dict] = []
        seen: set[str] = set()
        for item in list(incoming or []) + list(existing or []):
            if not isinstance(item, dict):
                continue
            transaction_id = str(item.get("transaction_id") or "").strip()
            if transaction_id and transaction_id in seen:
                continue
            if transaction_id:
                seen.add(transaction_id)
            merged.append(dict(item))
        return merged
