from __future__ import annotations

from core.exceptions import ValidationError


def validate_recipient(value: str) -> str:
    recipient = str(value or "").strip()
    if not recipient:
        raise ValidationError("Enter a recipient phone, email, or wallet ID.")
    return recipient


def validate_amount(value) -> float:
    try:
        amount = float(str(value or "").replace(",", "").strip())
    except Exception as exc:
        raise ValidationError("Enter a valid transfer amount.") from exc
    if amount <= 0:
        raise ValidationError("Transfer amount must be greater than zero.")
    return amount


def validate_pin(value: str) -> str:
    pin = str(value or "").strip()
    if len(pin) != 4 or not pin.isdigit():
        raise ValidationError("Enter a valid 4-digit PIN.")
    return pin
