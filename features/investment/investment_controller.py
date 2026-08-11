from datetime import datetime
from typing import Any, Dict, List

from features.investment.calculator import InvestmentCalculator
from features.investment.investment_service import InvestmentService
from features.investment.models import Investment
from features.investment.validators import validate_amount, validate_duration


def _items(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("items", "results", "investments", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    return []


def _progress_from_dates(start_text, end_text):
    try:
        start = datetime.fromisoformat(str(start_text).replace("Z", "+00:00"))
        end = datetime.fromisoformat(str(end_text).replace("Z", "+00:00"))
        now = datetime.utcnow()
        total = (end - start).total_seconds()
        if total <= 0:
            return 0
        elapsed = (now - start).total_seconds()
        return max(0, min(100, (elapsed / total) * 100))
    except Exception:
        return 0


class InvestmentController:
    DEFAULT_PLANS = [
        {"days": 60, "title": "60 Days", "subtitle": "Daily earnings", "detail": "Short-term growth"},
        {"days": 120, "title": "120 Days", "subtitle": "Recommended", "detail": "Balanced returns"},
        {"days": 245, "title": "245 Days", "subtitle": "Long term", "detail": "Compounding growth"},
        {"days": 365, "title": "365 Days", "subtitle": "Maximum growth", "detail": "Best long-term plan"},
    ]

    def __init__(self):
        self.service = InvestmentService()

    def load_dashboard(self):
        plans = self.normalize_plans(self._safe_call(self.service.plans, default=[]))
        if not plans:
            plans = [dict(item) for item in self.DEFAULT_PLANS]

        history = self.normalize_history(self._safe_call(self.service.history, default=[]))
        active = next((item for item in history if item.get("status_key") in {"active", "running", "ongoing"}), None)

        return {
            "plans": plans,
            "history": history,
            "active_investment": active,
        }

    def _safe_call(self, func, default):
        try:
            return func()
        except Exception:
            return default

    def normalize_plans(self, payload):
        items = _items(payload)
        if not items and isinstance(payload, list):
            items = payload
        normalized = []
        for item in items:
            days = int(item.get("days") or item.get("duration") or item.get("plan_days") or 0)
            if days <= 0:
                continue
            normalized.append(
                {
                    "plan_days": days,
                    "title": str(item.get("title") or f"{days} Days"),
                    "subtitle": str(item.get("subtitle") or item.get("tag") or ""),
                    "detail": str(item.get("detail") or item.get("description") or ""),
                    "status_text": str(item.get("status_text") or item.get("badge") or ""),
                    "selected": False,
                    "callback": None,
                }
            )
        return normalized

    def normalize_history(self, payload):
        items = _items(payload)
        normalized = []
        for item in items:
            investment = Investment.from_dict(item or {})
            start_raw = item.get("start_date") or item.get("created_at") or ""
            end_raw = item.get("end_date") or item.get("maturity_date") or ""
            status_key = investment.status.lower()
            normalized.append(
                {
                    "title": f"GH₵ {investment.amount:,.2f}",
                    "subtitle": f"{investment.duration} Days",
                    "detail": f"Earned GH₵ {investment.earned:,.2f}",
                    "status_text": investment.status.replace("_", " ").title(),
                    "status_key": status_key,
                    "created_at": f"{investment.start_date} - {investment.end_date}".strip(" -"),
                    "maturity_text": investment.end_date,
                    "plan_days": investment.duration,
                    "selected": False,
                    "callback": None,
                    "balance": investment.balance,
                    "progress": _progress_from_dates(start_raw, end_raw),
                }
            )
        return normalized

    def calculate_preview(self, amount, days):
        validated_amount = validate_amount(amount)
        validated_days = validate_duration(days)
        daily = InvestmentCalculator.calculate_daily(validated_amount)
        total = InvestmentCalculator.calculate_total(validated_amount, validated_days)
        return {
            "amount": validated_amount,
            "days": validated_days,
            "daily": daily,
            "total": total,
        }

    def start_investment(self, amount, days, available_balance=None, purpose=""):
        validated_amount = validate_amount(amount, available_balance=available_balance)
        validated_days = validate_duration(days)
        payload = {
            "amount": validated_amount,
            "duration": validated_days,
            "purpose": (purpose or "").strip(),
        }
        return self.service.create(payload)
