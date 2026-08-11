ALLOWED_DURATIONS = {60, 120, 245, 365}


def validate_amount(value, available_balance=None):
    amount = float(value)
    if amount < 10:
        raise ValueError("Minimum investment is GH₵10.")
    if amount > 1000:
        raise ValueError("Maximum investment is GH₵1000.")
    if available_balance is not None and amount > float(available_balance):
        raise ValueError("Insufficient wallet balance.")
    return amount


def validate_duration(value):
    duration = int(value)
    if duration not in ALLOWED_DURATIONS:
        raise ValueError("Select a valid investment duration.")
    return duration

