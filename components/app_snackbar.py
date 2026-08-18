from __future__ import annotations

from kivy.clock import Clock
from kivy.metrics import dp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDIcon, MDLabel

try:
    from kivymd.uix.snackbar import MDSnackbar, MDSnackbarText
except Exception:  # pragma: no cover - compatibility with older KivyMD builds
    from kivymd.uix.snackbar import MDSnackbar
    from kivymd.uix.label import MDLabel as MDSnackbarText

from theme import ERROR, INFO, PRIMARY, SUCCESS, SURFACE, TEXT_PRIMARY, TEXT_SECONDARY, WARNING


class AppSnackbar:
    """Shared snackbar helper for concise app notifications."""

    LEVELS = {
        "success": {
            "prefix": "✓",
            "icon": "check-circle-outline",
            "background": [0.07, 0.22, 0.14, 1],
            "accent": list(SUCCESS),
            "title": "Success",
        },
        "error": {
            "prefix": "✕",
            "icon": "close-circle-outline",
            "background": [0.22, 0.09, 0.10, 1],
            "accent": list(ERROR),
            "title": "Error",
        },
        "warning": {
            "prefix": "⚠",
            "icon": "alert-outline",
            "background": [0.22, 0.17, 0.06, 1],
            "accent": list(WARNING),
            "title": "Warning",
        },
        "info": {
            "prefix": "i",
            "icon": "information-outline",
            "background": [0.08, 0.14, 0.20, 1],
            "accent": list(INFO),
            "title": "Info",
        },
        "neutral": {
            "prefix": "",
            "icon": "message-text-outline",
            "background": list(SURFACE),
            "accent": list(PRIMARY),
            "title": "",
        },
    }

    @classmethod
    def _normalize_level(cls, level: str | None) -> str:
        value = str(level or "info").strip().lower()
        if value in {"ok", "done", "complete", "completed", "success"}:
            return "success"
        if value in {"fail", "failed", "error", "danger"}:
            return "error"
        if value in {"warn", "warning", "caution"}:
            return "warning"
        if value in {"info", "information"}:
            return "info"
        return value if value in cls.LEVELS else "info"

    @classmethod
    def _build_content(
        cls,
        *,
        message: str,
        level: str,
        title: str | None = None,
        icon: str | None = None,
    ):
        config = cls.LEVELS[cls._normalize_level(level)]
        root = MDBoxLayout(
            orientation="horizontal",
            spacing=dp(10),
            padding=[dp(14), dp(12), dp(14), dp(12)],
            adaptive_height=True,
        )
        icon_card = MDCard(
            size_hint=(None, None),
            size=(dp(32), dp(32)),
            radius=[dp(11)],
            md_bg_color=list(config["accent"]),
            elevation=0,
        )
        icon_card.add_widget(
            MDIcon(
                icon=str(icon or config["icon"]),
                theme_text_color="Custom",
                text_color=[0.05, 0.05, 0.05, 1],
                font_size="18sp",
                pos_hint={"center_x": 0.5, "center_y": 0.5},
            )
        )

        text_stack = MDBoxLayout(orientation="vertical", spacing=dp(2), adaptive_height=True)
        if title:
            text_stack.add_widget(
                MDLabel(
                    text=str(title),
                    theme_text_color="Custom",
                    text_color=list(TEXT_PRIMARY),
                    bold=True,
                    font_size="12sp",
                    adaptive_height=True,
                )
            )

        prefix = f"{config['prefix']} " if config["prefix"] else ""
        body = str(message or "").strip()
        if not body and title:
            body = str(title)
        elif body and title:
            body = f"{body}"
        snackbar_text = MDSnackbarText(
            text=f"{prefix}{body}".strip(),
            theme_text_color="Custom",
            text_color=list(TEXT_SECONDARY),
            font_size="13sp",
            adaptive_height=True,
        )
        text_stack.add_widget(snackbar_text)
        root.add_widget(icon_card)
        root.add_widget(text_stack)
        return root

    @staticmethod
    def show(
        message: str,
        *,
        level: str = "info",
        title: str | None = None,
        icon: str | None = None,
        duration: float = 2.2,
        sticky: bool = False,
    ):
        level_name = AppSnackbar._normalize_level(level)
        config = AppSnackbar.LEVELS[level_name]
        content = AppSnackbar._build_content(message=message, level=level_name, title=title, icon=icon)
        snackbar = MDSnackbar(content)

        if hasattr(snackbar, "md_bg_color"):
            snackbar.md_bg_color = list(config["background"])
        if hasattr(snackbar, "bg_color"):
            snackbar.bg_color = list(config["background"])
        if hasattr(snackbar, "line_color"):
            snackbar.line_color = list(config["accent"])
        if hasattr(snackbar, "text_color"):
            snackbar.text_color = list(TEXT_PRIMARY)

        snackbar.open()

        if not sticky and float(duration or 0) > 0:
            Clock.schedule_once(
                lambda _dt: snackbar.dismiss() if hasattr(snackbar, "dismiss") else None,
                float(duration),
            )
        return snackbar

    @staticmethod
    def success(message: str, *, duration: float = 2.2, sticky: bool = False):
        return AppSnackbar.show(message, level="success", duration=duration, sticky=sticky)

    @staticmethod
    def error(message: str, *, duration: float = 2.8, sticky: bool = False):
        return AppSnackbar.show(message, level="error", duration=duration, sticky=sticky)

    @staticmethod
    def warning(message: str, *, duration: float = 2.5, sticky: bool = False):
        return AppSnackbar.show(message, level="warning", duration=duration, sticky=sticky)

    @staticmethod
    def info(message: str, *, duration: float = 2.2, sticky: bool = False):
        return AppSnackbar.show(message, level="info", duration=duration, sticky=sticky)

    @staticmethod
    def notify(level: str, message: str, **kwargs):
        return AppSnackbar.show(message, level=level, **kwargs)


def show_app_snackbar(message: str, *, level: str = "info", title: str | None = None, icon: str | None = None, duration: float = 2.2, sticky: bool = False):
    return AppSnackbar.show(message, level=level, title=title, icon=icon, duration=duration, sticky=sticky)
