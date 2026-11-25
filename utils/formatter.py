from __future__ import annotations

import math
from datetime import datetime, timezone

from utils.constants import DEFAULT_CURRENCY


def safe_float(value, default: float | None = 0.0) -> float | None:
    if default is None:
        fallback = None
    else:
        try:
            fallback = float(default)
        except (TypeError, ValueError, OverflowError):
            fallback = 0.0
        if not math.isfinite(fallback):
            fallback = 0.0
    try:
        number = fallback if value is None or value == "" else float(value)
    except (TypeError, ValueError, OverflowError):
        return fallback
    if number is None:
        return None
    if not math.isfinite(number):
        return fallback
    return number


def _coerce_float(value, default: float = 0.0) -> float:
    return safe_float(value, default)


def format_currency(amount, currency: str = DEFAULT_CURRENCY, precision: int = 2) -> str:
    value = _coerce_float(amount)
    return f"- {currency} {abs(value):,.{precision}f}" if value < 0 else f"{currency} {value:,.{precision}f}"


def format_signed_currency(amount, currency: str = DEFAULT_CURRENCY, precision: int = 2) -> str:
    value = _coerce_float(amount)
    sign = "+" if value >= 0 else "-"
    return f"{sign} {currency} {abs(value):,.{precision}f}"


def format_datetime(value, default: str = "") -> str:
    if value is None or value == "":
        return default

    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        dt = None
        normalized = text.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(normalized)
        except Exception:
            for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    dt = datetime.strptime(text, pattern)
                    break
                except Exception:
                    continue
        if dt is None:
            return text or default

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%b %d, %Y %I:%M %p")


def shorten_text(value, limit: int = 32) -> str:
    text = str(value or "").strip()
    if limit <= 0 or len(text) <= limit:
        return text
    if limit <= 3:
        return text[:limit]
    return f"{text[: limit - 3].rstrip()}..."
