ALLOWED_DURATIONS = {30, 60, 90}


def validate_amount(value):
    amount = float(value)
    if amount <= 0:
        raise ValueError("Enter a valid loan amount.")
    return amount


def validate_duration(value):
    duration = int(value)
    if duration not in ALLOWED_DURATIONS:
        raise ValueError("Select a valid loan duration.")
    return duration

