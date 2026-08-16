from core.validation import validate_amount as core_validate_amount, validate_choice


SUPPORTED_METHODS = {"paystack", "mobile_money"}


def validate_amount(value) -> float:
    return core_validate_amount(value, label="amount")


def validate_method(value: str) -> str:
    return validate_choice(value, SUPPORTED_METHODS, label="payment method")
