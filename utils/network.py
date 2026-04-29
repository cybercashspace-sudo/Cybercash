def normalize_ghana_number(number: str) -> str:
    raw = "".join(ch for ch in str(number or "") if ch.isdigit() or ch == "+").strip()
    if raw.startswith("+233"):
        # +233241234567 -> 0241234567
        core = raw[4:]
        return f"0{core}" if core and not core.startswith("0") else core
    if raw.startswith("233"):
        core = raw[3:]
        return f"0{core}" if core and not core.startswith("0") else core
    # Support users entering mobile numbers without leading zero: 241234567 -> 0241234567.
    if raw.isdigit() and len(raw) == 9 and not raw.startswith("0"):
        return f"0{raw}"
    return raw


def detect_network(number: str):
    normalized = normalize_ghana_number(number)
    prefix = normalized[:3]

    mtn = ["024", "025", "053", "054", "055", "059"]
    telecel = ["020", "050"]
    airteltigo = ["026", "027", "056", "057"]

    if prefix in mtn:
        return "MTN"
    elif prefix in telecel:
        return "TELECEL"
    elif prefix in airteltigo:
        return "AIRTELTIGO"
    else:
        return "UNKNOWN"


def normalize_flutterwave_momo_number(number: str) -> str:
    normalized = normalize_ghana_number(number)
    digits = "".join(ch for ch in normalized if ch.isdigit())

    if digits.startswith("0") and len(digits) == 10:
        return f"233{digits[1:]}"

    if digits.startswith("233") and len(digits) == 12:
        return digits

    if len(digits) == 9:
        return f"233{digits}"

    return digits


def detect_flutterwave_network(number: str) -> str:
    normalized = normalize_ghana_number(number)
    prefix = normalized[:3]

    mtn = ["024", "025", "053", "054", "055", "059"]
    vodafone = ["020", "050"]
    airteltigo = ["026", "027", "056", "057"]

    if prefix in mtn:
        return "MTN"
    if prefix in vodafone:
        return "VODAFONE"
    if prefix in airteltigo:
        return "AIRTELTIGO"
    return "UNKNOWN"


def is_valid_flutterwave_momo_number(number: str) -> bool:
    normalized = normalize_ghana_number(number)
    digits = "".join(ch for ch in normalized if ch.isdigit())
    return len(digits) == 10 and detect_flutterwave_network(digits) != "UNKNOWN"
