from typing import Any, Dict, List

from features.loans.loan_calculator import LoanCalculator
from features.loans.loan_service import LoanService
from features.loans.models import Loan
from features.loans.validators import validate_amount, validate_duration


def _items(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("items", "results", "repayments", "data", "loans"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    return []


class LoanController:
    def __init__(self):
        self.service = LoanService()

    def load_dashboard(self):
        eligibility = self._safe_call(self.service.check_eligibility, default={})
        repayments = self.normalize_repayments(self._safe_call(self.service.repayments, default=[]))
        active = self._extract_active_loan(eligibility, repayments)

        available_credit = self._pick_value(eligibility, ("available_credit", "credit_limit", "max_amount"), 0.0)
        current_loan = self._pick_value(eligibility, ("current_loan", "loan_amount", "amount"), 0.0)
        status = str(eligibility.get("status") or (active or {}).get("status_text") or "Pending")
        next_payment = str(eligibility.get("next_payment") or (active or {}).get("next_payment_text") or "")

        return {
            "eligibility": eligibility,
            "available_credit": float(available_credit or 0.0),
            "available_credit_text": f"GH₵ {float(available_credit or 0.0):,.2f}",
            "current_loan": float(current_loan or 0.0),
            "current_loan_text": f"GH₵ {float(current_loan or 0.0):,.2f}",
            "status_text": status.replace("_", " ").title(),
            "next_payment_text": next_payment,
            "repayments": repayments,
            "active_loan": active,
        }

    def _pick_value(self, payload, keys, default=0.0):
        for key in keys:
            if isinstance(payload, dict) and payload.get(key) is not None:
                return payload.get(key)
        return default

    def _safe_call(self, func, default):
        try:
            return func()
        except Exception:
            return default

    def _extract_active_loan(self, eligibility, repayments):
        loan_data = None
        if isinstance(eligibility, dict):
            loan_data = eligibility.get("loan") or eligibility.get("active_loan")
        if loan_data:
            loan = Loan.from_dict(loan_data)
            return self._normalize_loan(loan)
        for item in repayments:
            if item.get("status_key") in {"active", "approved", "disbursed"}:
                return item
        return None

    def _normalize_loan(self, loan):
        return {
            "title": f"GH₵ {loan.amount:,.2f}",
            "subtitle": f"{loan.duration} Days",
            "detail": f"Balance GH₵ {loan.balance:,.2f}",
            "status_text": loan.status.replace("_", " ").title(),
            "status_key": loan.status.lower(),
            "next_payment_text": loan.next_payment,
        }

    def normalize_repayments(self, payload):
        items = _items(payload)
        normalized = []
        for item in items:
            loan = Loan.from_dict(item or {})
            normalized.append(
                {
                    "transaction_id": str(item.get("id") or item.get("repayment_id") or ""),
                    "title": f"GH₵ {loan.amount:,.2f}",
                    "amount_text": f"- GH₵ {loan.amount:,.2f}",
                    "subtitle": f"{loan.duration} Days",
                    "detail": f"Balance GH₵ {loan.balance:,.2f}",
                    "description": str(item.get("purpose") or item.get("description") or ""),
                    "status_text": loan.status.replace("_", " ").title(),
                    "status_key": loan.status.lower(),
                    "date_text": loan.created_at,
                    "created_at": loan.created_at,
                    "next_payment_text": loan.next_payment,
                    "reference": str(item.get("reference") or ""),
                    "plan_days": loan.duration,
                }
            )
        return normalized

    def apply_loan(self, amount, duration, purpose=""):
        validated_amount = validate_amount(amount)
        validated_duration = validate_duration(duration)
        payload = {
            "amount": validated_amount,
            "duration": validated_duration,
            "purpose": (purpose or "").strip(),
        }
        return self.service.apply(payload)

    def calculate_remaining(self, principal, paid):
        return LoanCalculator.remaining(principal, paid)

