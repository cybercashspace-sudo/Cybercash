from core.validation import (
    validate_amount as core_validate_amount,
    validate_pin as core_validate_pin,
    validate_recipient as core_validate_recipient,
)


def validate_recipient(value: str) -> str:
    return core_validate_recipient(value)


def validate_amount(value) -> float:
    return core_validate_amount(value, label="transfer amount")


def validate_pin(value: str) -> str:
    return core_validate_pin(value)
