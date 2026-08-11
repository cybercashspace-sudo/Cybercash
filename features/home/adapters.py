from __future__ import annotations


class TransactionAdapter:
    @staticmethod
    def format(item: dict) -> dict:
        payload = dict(item or {})
        return {
            "title": str(payload.get("title") or payload.get("type") or "Transaction"),
            "amount": payload.get("amount", 0),
            "date": str(payload.get("created_at") or payload.get("date") or payload.get("timestamp") or ""),
            "status": str(payload.get("status") or payload.get("state") or "completed"),
            "direction": str(payload.get("direction") or payload.get("flow") or ""),
            "raw": payload,
        }
