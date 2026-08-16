from __future__ import annotations

from kivymd.uix.snackbar import MDSnackbar, MDSnackbarText


class AppSnackbar:
    """Shared snackbar helper for concise app notifications."""

    @staticmethod
    def show(message: str, *, title: str | None = None):
        text = str(message or "").strip()
        if title:
            text = f"{title}: {text}" if text else str(title)
        snackbar = MDSnackbar(MDSnackbarText(text=text or ""))
        snackbar.open()
        return snackbar

    @staticmethod
    def success(message: str):
        return AppSnackbar.show(message, title="Success")

    @staticmethod
    def error(message: str):
        return AppSnackbar.show(message, title="Error")

    @staticmethod
    def warning(message: str):
        return AppSnackbar.show(message, title="Warning")

    @staticmethod
    def info(message: str):
        return AppSnackbar.show(message)


def show_app_snackbar(message: str, *, title: str | None = None):
    return AppSnackbar.show(message, title=title)
