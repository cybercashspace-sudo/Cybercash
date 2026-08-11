import re


def normalize_phone(phone):
    digits = re.sub(r"\D", "", phone or "")
    if digits.startswith("233") and len(digits) >= 12:
        digits = "0" + digits[3:]
    if len(digits) != 10:
        raise ValueError("Enter a valid Ghana mobile number.")
    return digits


def validate_amount(value):
    amount = float(value)
    if amount <= 0:
        raise ValueError("Enter an amount greater than zero.")
    return amount


def validate_network(network):
    cleaned = (network or "").strip()
    if not cleaned or cleaned.lower() == "unknown":
        raise ValueError("Select a valid mobile network.")
    return cleaned

