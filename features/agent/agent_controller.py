from typing import Any, Dict, List

from features.agent.agent_service import AgentService
from features.agent.models import Agent, AgentTransaction
from features.agent.validators import (
    validate_id_number,
    validate_name,
    validate_phone,
    validate_positive_amount,
)


def _items(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("items", "results", "transactions", "data", "history"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    return []


class AgentController:
    def __init__(self):
        self.service = AgentService()

    def load_dashboard(self):
        profile = self._safe_call(self.service.profile, default={})
        commissions = self._safe_call(self.service.commissions, default={})
        transactions = self.normalize_transactions(self._safe_call(self.service.transactions, default=[]))
        agent = Agent.from_dict(profile or {})
        return {
            "agent": self.normalize_agent(agent),
            "commissions": self.normalize_commissions(commissions),
            "transactions": transactions,
        }

    def normalize_agent(self, agent):
        return {
            "name": agent.name,
            "status": agent.status.replace("_", " ").title(),
            "verified": bool(agent.verified),
            "commission_text": f"GH₵ {float(agent.commission or 0.0):,.2f}",
            "today_sales_text": f"GH₵ {float(agent.today_sales or 0.0):,.2f}",
            "customers_served_text": str(int(agent.customers_served or 0)),
            "wallet_balance_text": f"GH₵ {float(agent.wallet_balance or 0.0):,.2f}",
        }

    def normalize_commissions(self, payload):
        summary = payload if isinstance(payload, dict) else {}
        history = self.normalize_transactions(_items(payload))
        return {
            "today_text": f"GH₵ {float(summary.get('today') or summary.get('today_total') or 0.0):,.2f}",
            "week_text": f"GH₵ {float(summary.get('week') or summary.get('week_total') or 0.0):,.2f}",
            "total_text": f"GH₵ {float(summary.get('total') or summary.get('total_earned') or 0.0):,.2f}",
            "history": history,
        }

    def normalize_transactions(self, payload):
        items = _items(payload)
        normalized = []
        for item in items:
            tx = AgentTransaction.from_dict(item or {})
            normalized.append(
                {
                    "transaction_id": tx.transaction_id,
                    "title": tx.title,
                    "amount_text": tx.amount_text,
                    "status_text": tx.status_text,
                    "date_text": tx.date_text,
                    "description": tx.description,
                    "created_at": tx.date_text,
                    "reference": tx.transaction_id,
                }
            )
        return normalized

    def apply_for_agent(self, name, phone, id_number, note=""):
        payload = {
            "name": validate_name(name),
            "phone": validate_phone(phone),
            "id_number": validate_id_number(id_number),
            "note": (note or "").strip(),
        }
        return self.service.apply(payload)

    def commission_summary(self):
        return self.normalize_commissions(self._safe_call(self.service.commissions, default={}))

    def transaction_history(self):
        return self.normalize_transactions(self._safe_call(self.service.transactions, default=[]))

    def api_keys(self):
        return self.service.api_keys()

    def create_api_key(self, name: str, mode: str = "live"):
        return self.service.create_api_key(name, mode)

    def revoke_api_key(self, key_id: int):
        return self.service.revoke_api_key(key_id)

    def _safe_call(self, func, default):
        try:
            return func()
        except Exception:
            return default

