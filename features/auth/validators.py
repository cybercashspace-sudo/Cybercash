from __future__ import annotations

import re

from core.exceptions import ValidationError


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\+?[0-9][0-9\s\-]{6,}$")
PIN_RE = re.compile(r"^\d{4}$")


def normalize_identifier(value: str) -> str:
    return str(value or "").strip()


def validate_identifier(value: str) -> str:
    identifier = normalize_identifier(value)
    if not identifier:
        raise ValidationError("Enter your email or phone number.")
    if EMAIL_RE.match(identifier) or PHONE_RE.match(identifier):
        return identifier
    return identifier


def validate_password(value: str) -> str:
    password = str(value or "").strip()
    if not password:
        raise ValidationError("Enter your password.")
    if len(password) < 4:
        raise ValidationError("Password is too short.")
    return password


def validate_pin(value: str) -> str:
    pin = str(value or "").strip()
    if not PIN_RE.match(pin):
        raise ValidationError("PIN must be exactly 4 digits.")
    return pin


def validate_confirmation(password: str, confirmation: str) -> str:
    password = validate_password(password)
    confirmation = str(confirmation or "").strip()
    if password != confirmation:
        raise ValidationError("Passwords do not match.")
    return confirmation
