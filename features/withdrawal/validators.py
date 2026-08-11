from __future__ import annotations

from core.exceptions import ValidationError


SUPPORTED_NETWORKS = {"mtn", "telecel", "airteltigo", "auto"}


def validate_amount(value) -> float:
    try:
        amount = float(str(value or "").replace(",", "").strip())
    except Exception as exc:
        raise ValidationError("Enter a valid withdrawal amount.") from exc
    if amount <= 0:
        raise ValidationError("Withdrawal amount must be greater than zero.")
    return amount


def validate_phone(value: str) -> str:
    phone = str(value or "").strip()
    if len(phone) < 10:
        raise ValidationError("Enter a valid mobile money number.")
    return phone


def validate_pin(value: str) -> str:
    pin = str(value or "").strip()
    if len(pin) != 4 or not pin.isdigit():
        raise ValidationError("Enter a valid 4-digit PIN.")
    return pin


def validate_network(value: str) -> str:
    network = str(value or "").strip().lower()
    if network not in SUPPORTED_NETWORKS:
        raise ValidationError("Select a valid mobile network.")
    return network


def detect_network(phone: str) -> str:
    phone = str(phone or "").strip()
    prefixes = {
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
    return prefixes.get(phone[:3], "auto")
