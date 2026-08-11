import re


def validate_btc_amount(value):
    amount = float(value)
    if amount <= 0:
        raise ValueError("BTC amount must be greater than zero.")
    return amount


def validate_btc_address(address):
    cleaned = (address or "").strip()
    if len(cleaned) < 26 or len(cleaned) > 120:
        raise ValueError("Enter a valid BTC address.")
    if not re.fullmatch(r"[A-Za-z0-9]{26,120}", cleaned):
        raise ValueError("Enter a valid BTC address.")
    return cleaned

