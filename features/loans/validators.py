from core.validation import validate_amount as core_validate_amount, validate_duration as core_validate_duration


ALLOWED_DURATIONS = {30, 60, 90}


def validate_amount(value):
    return core_validate_amount(
        value,
        label="loan amount",
        invalid_message="Enter a valid loan amount.",
        minimum_message="Enter a valid loan amount.",
    )


def validate_duration(value):
    return core_validate_duration(value, ALLOWED_DURATIONS, label="loan duration")
