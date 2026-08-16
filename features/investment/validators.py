from core.validation import validate_amount as core_validate_amount, validate_duration as core_validate_duration


ALLOWED_DURATIONS = {60, 120, 245, 365}


def validate_amount(value, available_balance=None):
    return core_validate_amount(
        value,
        label="investment amount",
        minimum=10,
        maximum=1000,
        available_balance=available_balance,
        invalid_message="Enter a valid investment amount.",
        minimum_message="Minimum investment is GHS 10.",
        maximum_message="Maximum investment is GHS 1000.",
        available_balance_message="Insufficient wallet balance.",
    )


def validate_duration(value):
    return core_validate_duration(value, ALLOWED_DURATIONS, label="investment duration")
