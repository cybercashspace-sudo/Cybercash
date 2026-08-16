from __future__ import annotations

from kivy.utils import get_color_from_hex

from .animations import COUNTER, FAST, HERO, MEDIUM, NORMAL, SHIMMER, SLOW, SPRING, STANDARD
from .colors import (
    BACKGROUND,
    BACKGROUND_LIGHT,
    BORDER,
    BTC,
    CARD,
    DIVIDER,
    ERROR,
    GLASS_BG,
    GLASS_BORDER,
    GREEN,
    INFO,
    PRIMARY,
    PRIMARY_DARK,
    PRIMARY_LIGHT,
    RED,
    SUCCESS,
    SURFACE,
    TEXT_HINT,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    WARNING,
)
from .elevation import HIGH, LOW, MEDIUM as ELEVATION_MEDIUM
from .radius import BUTTON_RADIUS, CARD_RADIUS, PILL_RADIUS, SHEET_RADIUS
from .spacing import CARD_PADDING, SCREEN_PADDING, SPACE_LG, SPACE_MD, SPACE_SM, SPACE_XL, SPACE_XS
from .typography import BODY, CAPTION, DISPLAY, HEADLINE, LABEL, TITLE


APP_NAME = "CYBER CASH"


class CyberTheme:
    GOLD = PRIMARY
    EMERALD = get_color_from_hex("#3CB371")
    DARK_BG = BACKGROUND
    CARD_BG = CARD
    SUCCESS = SUCCESS
    ERROR = ERROR
    BTC = BTC


__all__ = [
    "APP_NAME",
    "CyberTheme",
    "BACKGROUND",
    "BACKGROUND_LIGHT",
    "BORDER",
    "BTC",
    "BUTTON_RADIUS",
    "BODY",
    "CARD",
    "CARD_PADDING",
    "CARD_RADIUS",
    "CAPTION",
    "COUNTER",
    "DISPLAY",
    "DIVIDER",
    "ERROR",
    "FAST",
    "HERO",
    "GLASS_BG",
    "GLASS_BORDER",
    "GREEN",
    "HEADLINE",
    "HIGH",
    "INFO",
    "LABEL",
    "LOW",
    "MEDIUM",
    "ELEVATION_MEDIUM",
    "NORMAL",
    "PILL_RADIUS",
    "PRIMARY",
    "PRIMARY_DARK",
    "PRIMARY_LIGHT",
    "RED",
    "SCREEN_PADDING",
    "SHIMMER",
    "SHEET_RADIUS",
    "SLOW",
    "SPACE_LG",
    "SPACE_MD",
    "SPACE_SM",
    "SPACE_XL",
    "SPACE_XS",
    "SPRING",
    "STANDARD",
    "SUCCESS",
    "SURFACE",
    "TEXT_HINT",
    "TEXT_PRIMARY",
    "TEXT_SECONDARY",
    "TITLE",
    "WARNING",
]
