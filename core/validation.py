from __future__ import annotations

import re
from collections.abc import Iterable

from core.exceptions import ValidationError


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
BTC_ADDRESS_RE = re.compile(r"^[A-Za-z0-9]{26,120}$")

GHANA_NETWORK_PREFIXES = {
    "024": "mtn",
    "025": "mtn",
    "053": "mtn",
    "054": "mtn",
    "055": "mtn",
    "059": "mtn",
    "020": "telecel",
    "050": "telecel",
    "026": "airteltigo",
    "027": "airteltigo",
    "056": "airteltigo",
    "057": "airteltigo",
}


def _text(value) -> str:
    return str(value or "").strip()


def _display_label(label: str, fallback: str = "value") -> str:
    cleaned = _text(label)
    return cleaned or fallback


def validate_non_empty(value, *, message: str | None = None, label: str = "value") -> str:
    text = _text(value)
    if not text:
        raise ValidationError(message or f"Enter {label}.")
    return text


def validate_name(
    value,
    *,
    message: str | None = None,
    label: str = "name",
    minimum: int = 2,
) -> str:
    text = _text(value)
    if len(text) < int(minimum or 0):
        raise ValidationError(message or f"Enter a valid {label}.")
    return text


def validate_id_number(
    value,
    *,
    message: str | None = None,
    label: str = "ID number",
    minimum: int = 5,
) -> str:
    text = _text(value)
    if len(text) < int(minimum or 0):
        raise ValidationError(message or f"Enter a valid {label}.")
    return text


def validate_email(value, *, message: str | None = None) -> str:
    email = _text(value)
    if not email or not EMAIL_RE.fullmatch(email):
        raise ValidationError(message or "Enter a valid email address.")
    return email


def validate_identifier(value, *, message: str | None = None) -> str:
    return validate_non_empty(
        value,
        message=message or "Enter your email or phone number.",
        label="identifier",
    )


def validate_password(value, *, message: str | None = None, minimum: int = 4) -> str:
    password = _text(value)
    if not password:
        raise ValidationError(message or "Enter your password.")
    if len(password) < int(minimum or 0):
        raise ValidationError(message or "Password is too short.")
    return password


def validate_confirmation(password: str, confirmation: str, *, message: str | None = None) -> str:
    password_value = validate_password(password)
    confirmation_value = _text(confirmation)
    if password_value != confirmation_value:
        raise ValidationError(message or "Passwords do not match.")
    return confirmation_value


def normalize_phone(value, *, label: str = "phone number", message: str | None = None) -> str:
    phone = _text(value)
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("233") and len(digits) >= 12:
        digits = "0" + digits[3:]
    if len(digits) != 10:
        raise ValidationError(message or f"Enter a valid {label}.")
    return digits


def validate_phone(value, *, label: str = "phone number", message: str | None = None) -> str:
    return normalize_phone(value, label=label, message=message)


def validate_pin(value, *, digits: int = 4, message: str | None = None) -> str:
    pin = _text(value)
    if len(pin) != int(digits or 0) or not pin.isdigit():
        raise ValidationError(message or f"Enter a valid {int(digits or 0)}-digit PIN.")
    return pin


def _minimum_message(label: str, minimum: float) -> str:
    display = _display_label(label, "amount").capitalize()
    if minimum <= 0.01:
        return f"{display} must be greater than zero."
    return f"{display} must be at least {minimum:,.2f}."


def validate_amount(
    value,
    *,
    label: str = "amount",
    minimum: float = 0.01,
    maximum: float | None = None,
    available_balance: float | None = None,
    invalid_message: str | None = None,
    minimum_message: str | None = None,
    maximum_message: str | None = None,
    available_balance_message: str | None = None,
) -> float:
    text = _text(value).replace(",", "")
    try:
        amount = float(text)
    except Exception as exc:
        raise ValidationError(invalid_message or f"Enter a valid {_display_label(label, 'amount')}.") from exc

    if amount < float(minimum):
        raise ValidationError(minimum_message or _minimum_message(label, float(minimum)))

    if maximum is not None and amount > float(maximum):
        raise ValidationError(maximum_message or f"{_display_label(label, 'Amount').capitalize()} must be {float(maximum):,.2f} or less.")

    if available_balance is not None and amount > float(available_balance):
        raise ValidationError(available_balance_message or "Insufficient wallet balance.")

    return amount


def validate_positive_amount(value, *, label: str = "amount", message: str | None = None) -> float:
    return validate_amount(
        value,
        label=label,
        minimum=0.01,
        invalid_message=message,
        minimum_message=message,
    )


def validate_choice(
    value,
    choices: Iterable[str],
    *,
    label: str = "value",
    message: str | None = None,
) -> str:
    choice = _text(value).lower()
    allowed = {str(item).strip().lower() for item in choices if str(item).strip()}
    if choice not in allowed:
        raise ValidationError(message or f"Select a valid {label}.")
    return choice


def validate_network(
    value,
    supported: Iterable[str] | None = None,
    *,
    label: str = "mobile network",
    message: str | None = None,
) -> str:
    allowed = supported or {"mtn", "telecel", "airteltigo"}
    return validate_choice(value, allowed, label=label, message=message)


def detect_ghana_network(phone: str) -> str:
    digits = re.sub(r"\D", "", _text(phone))
    return GHANA_NETWORK_PREFIXES.get(digits[:3], "auto")


def validate_recipient(value, *, message: str | None = None) -> str:
    return validate_non_empty(
        value,
        message=message or "Enter a recipient phone, email, or wallet ID.",
        label="recipient",
    )


def validate_wallet_id(value, *, message: str | None = None) -> str:
    return validate_non_empty(value, message=message or "Enter a valid wallet ID.", label="wallet ID")


def validate_btc_amount(value, *, message: str | None = None) -> float:
    return validate_amount(
        value,
        label="BTC amount",
        minimum=0.00000001,
        invalid_message=message or "Enter a valid BTC amount.",
        minimum_message=message or "BTC amount must be greater than zero.",
    )


def validate_btc_address(value, *, message: str | None = None) -> str:
    address = _text(value)
    if len(address) < 26 or len(address) > 120 or not BTC_ADDRESS_RE.fullmatch(address):
        raise ValidationError(message or "Enter a valid BTC address.")
    return address


def validate_duration(
    value,
    allowed: Iterable[int],
    *,
    label: str = "duration",
    message: str | None = None,
) -> int:
    try:
        duration = int(str(value or "").strip())
    except Exception as exc:
        raise ValidationError(message or f"Select a valid {label}.") from exc

    allowed_values = {int(item) for item in allowed}
    if duration not in allowed_values:
        raise ValidationError(message or f"Select a valid {label}.")
    return duration
