from __future__ import annotations

from core.exceptions import ValidationError


SUPPORTED_METHODS = {"paystack", "mobile_money"}


def validate_amount(value) -> float:
    try:
        amount = float(str(value or "").replace(",", "").strip())
    except Exception as exc:
        raise ValidationError("Enter a valid amount.") from exc
    if amount <= 0:
        raise ValidationError("Amount must be greater than zero.")
    return amount


def validate_method(value: str) -> str:
    method = str(value or "").strip().lower()
    if method not in SUPPORTED_METHODS:
        raise ValidationError("Select a valid payment method.")
    return method
