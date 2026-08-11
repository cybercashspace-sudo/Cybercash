from __future__ import annotations

import logging
from logging import Logger


def setup_logging(level: int = logging.INFO) -> None:
    if getattr(setup_logging, "_configured", False):
        return
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.raiseExceptions = False
    setup_logging._configured = True  # type: ignore[attr-defined]


def get_logger(name: str) -> Logger:
    setup_logging()
    return logging.getLogger(name)

