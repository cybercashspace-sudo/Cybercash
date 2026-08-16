from core.validation import (
    detect_ghana_network,
    validate_amount as core_validate_amount,
    validate_network as core_validate_network,
    validate_phone as core_validate_phone,
    validate_pin as core_validate_pin,
)


SUPPORTED_NETWORKS = {"mtn", "telecel", "airteltigo", "auto"}


def validate_amount(value) -> float:
    return core_validate_amount(value, label="withdrawal amount")


def validate_phone(value: str) -> str:
    return core_validate_phone(value, label="mobile money number")


def validate_pin(value: str) -> str:
    return core_validate_pin(value)


def validate_network(value: str) -> str:
    return core_validate_network(value, SUPPORTED_NETWORKS, label="mobile network")


def detect_network(phone: str) -> str:
    return detect_ghana_network(phone)
