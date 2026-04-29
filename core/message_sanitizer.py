from __future__ import annotations

import re
from typing import Any

DEFAULT_FALLBACK_MESSAGE = "Please try again."
GENERIC_SERVER_MESSAGE = "Something went wrong on the server. Please try again."
GENERIC_CONNECTION_MESSAGE = "We could not reach the server. Check your connection and try again."
GENERIC_TIMEOUT_MESSAGE = "The request took too long. Please try again."
GENERIC_BACKEND_UNAVAILABLE_MESSAGE = "The service is temporarily unavailable. Please try again later."
PAYSTACK_UNAVAILABLE_MESSAGE = "The payment service is temporarily unavailable. Please try again later."

_LIST_ITEM_KEYS = ("msg", "detail", "message", "error")

_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"could not validate credentials|invalid credentials", re.I), "The details you entered do not match an account. Please try again."),
    (re.compile(r"account not verified|complete otp verification|verification required", re.I), "Please verify your account with the OTP code before signing in."),
    (re.compile(r"invalid otp|otp expired|otp session expired", re.I), "That OTP is not correct or has expired. Request a new code and try again."),
    (re.compile(r"number already registered|phone number already registered", re.I), "This MoMo number already has an account. Please sign in instead."),
    (re.compile(r"pending admin approval|pending approval", re.I), "Your account is pending approval. Please try again after review is complete."),
    (re.compile(r"temporarily locked|failed pin attempts", re.I), "Too many incorrect PIN attempts were entered. Please wait a few minutes and try again."),
    (re.compile(r"agent registration requires", re.I), "To open an agent account, add your business name, Ghana Card ID, and agent location."),
    (re.compile(r"unauthorized|forbidden", re.I), "Please sign in again to continue."),
    (re.compile(r"unable to connect to the remote server|connection refused|max retries exceeded|connection reset|connection aborted", re.I), GENERIC_CONNECTION_MESSAGE),
    (re.compile(r"timed out|timeout", re.I), GENERIC_TIMEOUT_MESSAGE),
    (re.compile(r"internal server error|http 500|http 502|http 503|service unavailable", re.I), GENERIC_SERVER_MESSAGE),
    (re.compile(r"database system is starting up|cannot connect now|could not connect to server", re.I), GENERIC_BACKEND_UNAVAILABLE_MESSAGE),
    (re.compile(r"traceback|unboundlocalerror|attributeerror|keyerror|typeerror|valueerror|runtimeerror", re.I), GENERIC_SERVER_MESSAGE),
    (re.compile(r"paystack authentication failed|paystack secret key is not configured", re.I), PAYSTACK_UNAVAILABLE_MESSAGE),
    (re.compile(r"paystack network error|paystack service unavailable", re.I), PAYSTACK_UNAVAILABLE_MESSAGE),
    (re.compile(r"unable to start paystack checkout right now|unable to verify paystack payment right now", re.I), PAYSTACK_UNAVAILABLE_MESSAGE),
)


def _normalize_text(value: Any) -> str:
    text = str(value or "").replace("\\n", "\n").replace("\r", "\n").strip()
    if not text:
        return ""
    return text


def _extract_first_message_from_list(items: list[Any]) -> str:
    values: list[str] = []
    for item in items:
        if isinstance(item, dict):
            values.append(_normalize_text(next((item.get(key) for key in _LIST_ITEM_KEYS if item.get(key)), item)))
        else:
            values.append(_normalize_text(item))
    return ", ".join(value for value in values if value)


def sanitize_backend_message(message: Any, fallback: str = DEFAULT_FALLBACK_MESSAGE) -> str:
    text = _normalize_text(message)
    if not text:
        return str(fallback or DEFAULT_FALLBACK_MESSAGE)

    collapsed = re.sub(r"\s+", " ", text).strip()
    lower = collapsed.lower()

    if lower.startswith("paystack rejected request:"):
        remainder = text.split(":", 1)[1].strip()
        return sanitize_backend_message(remainder, fallback=PAYSTACK_UNAVAILABLE_MESSAGE)

    for pattern, replacement in _RULES:
        if pattern.search(lower):
            return replacement

    if lower.startswith("request failed (") or lower.startswith("agent profile sync unavailable (") or lower.startswith("summary sync unavailable (") or lower.startswith("history sync unavailable ("):
        return GENERIC_CONNECTION_MESSAGE

    if "httpconnectionpool" in lower or "urllib3" in lower:
        return GENERIC_CONNECTION_MESSAGE

    if "exception" in lower or "error:" in lower:
        return GENERIC_SERVER_MESSAGE

    return text


def extract_backend_message(payload: Any, fallback: str = DEFAULT_FALLBACK_MESSAGE) -> str:
    if isinstance(payload, dict):
        for key in ("detail", "message", "error", "msg"):
            value = payload.get(key)
            if value:
                if isinstance(value, list):
                    return sanitize_backend_message(_extract_first_message_from_list(value), fallback=fallback)
                if isinstance(value, dict):
                    nested = next((value.get(key) for key in _LIST_ITEM_KEYS if value.get(key)), value)
                    return sanitize_backend_message(nested, fallback=fallback)
                return sanitize_backend_message(value, fallback=fallback)
        return sanitize_backend_message(fallback, fallback=fallback)

    if isinstance(payload, list):
        return sanitize_backend_message(_extract_first_message_from_list(payload), fallback=fallback)

    return sanitize_backend_message(payload, fallback=fallback)
