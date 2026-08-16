from core.validation import (
    normalize_phone,
    validate_amount as core_validate_amount,
    validate_id_number as core_validate_id_number,
    validate_name as core_validate_name,
)


def validate_name(value):
    return core_validate_name(value, message="Enter the agent's full name.")


def validate_phone(value):
    return normalize_phone(value, label="Ghana phone number", message="Enter a valid Ghana phone number.")


def validate_id_number(value):
    return core_validate_id_number(value, message="Enter a valid ID number.")


def validate_positive_amount(value, label="amount"):
    return core_validate_amount(
        value,
        label=label,
        invalid_message=f"Enter a valid {label}.",
        minimum_message=f"Enter a valid {label}.",
    )
