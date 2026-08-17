from __future__ import annotations

import logging
import re
from logging import Logger

from core.message_sanitizer import sanitize_backend_message


_SENSITIVE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?i)(access[_-]?token|refresh[_-]?token|token|pin|password|otp)\s*[:=]\s*['\"]?[^'\"\s,}]+"), r"\1=<redacted>"),
    (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9\-._~+/]+=*"), r"\1<redacted>"),
)


def _redact_sensitive_text(message: str) -> str:
    text = str(message or "")
    for pattern, replacement in _SENSITIVE_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


class StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        timestamp = self.formatTime(record, self.datefmt)
        feature = str(getattr(record, "feature", record.name) or record.name).strip()
        request_id = str(getattr(record, "request_id", "") or "").strip()
        message = _redact_sensitive_text(sanitize_backend_message(record.getMessage(), fallback=record.getMessage()))
        parts = [timestamp, record.levelname, feature]
        if request_id:
            parts.append(f"request_id={request_id}")
        parts.append(message)
        output = " ".join(part for part in parts if part)
        if record.exc_info:
            output = f"{output}\n{self.formatException(record.exc_info)}"
        return output


class SensitiveDataFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
            redacted = _redact_sensitive_text(message)
            record.msg = redacted
            record.args = ()
        except Exception:
            pass
        return True


def setup_logging(level: int = logging.INFO) -> None:
    if getattr(setup_logging, "_configured", False):
        return

    root = logging.getLogger()
    root.setLevel(level)

    formatter = StructuredFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    handler = None
    if not root.handlers:
        handler = logging.StreamHandler()
        root.addHandler(handler)
    else:
        for existing_handler in root.handlers:
            existing_handler.setFormatter(formatter)

    if handler is not None:
        handler.setFormatter(formatter)

    root.addFilter(SensitiveDataFilter())
    logging.raiseExceptions = False
    setup_logging._configured = True  # type: ignore[attr-defined]


def get_logger(name: str) -> Logger:
    setup_logging()
    return logging.getLogger(name)
