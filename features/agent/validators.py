import re


def validate_name(value):
    text = (value or "").strip()
    if len(text) < 2:
        raise ValueError("Enter the agent's full name.")
    return text


def validate_phone(value):
    digits = re.sub(r"\D", "", value or "")
    if digits.startswith("233") and len(digits) >= 12:
        digits = "0" + digits[3:]
    if len(digits) != 10:
        raise ValueError("Enter a valid Ghana phone number.")
    return digits


def validate_id_number(value):
    text = (value or "").strip()
    if len(text) < 5:
        raise ValueError("Enter a valid ID number.")
    return text


def validate_positive_amount(value, label="amount"):
    amount = float(value)
    if amount <= 0:
        raise ValueError(f"Enter a valid {label}.")
    return amount

