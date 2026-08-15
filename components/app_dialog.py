from __future__ import annotations

from kivy.metrics import dp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.label import MDLabel

from core.popup_manager import show_confirm_dialog, show_custom_dialog, show_message_dialog


class AppDialog:
    """Shared dialog facade for consistent success, error, confirmation, and loading states."""

    @staticmethod
    def success(owner, title: str, message: str, *, on_close=None):
        return show_message_dialog(owner, title=title, message=message, close_label="OK", on_close=on_close)

    @staticmethod
    def error(owner, title: str, message: str, *, on_close=None):
        return show_message_dialog(owner, title=title, message=message, close_label="Close", on_close=on_close)

    @staticmethod
    def confirm(owner, title: str, message: str, *, on_confirm, confirm_label: str = "Confirm", cancel_label: str = "Cancel"):
        return show_confirm_dialog(
            owner,
            title=title,
            message=message,
            on_confirm=on_confirm,
            confirm_label=confirm_label,
            cancel_label=cancel_label,
        )

    @staticmethod
    def loading(owner, title: str = "Loading", message: str = "Please wait..."):
        content = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=dp(10), padding=[dp(16), dp(16), dp(16), dp(16)])
        content.add_widget(
            MDLabel(
                text=str(message or "Please wait..."),
                halign="center",
                theme_text_color="Hint",
                adaptive_height=True,
            )
        )
        return show_custom_dialog(owner, title=title, content_cls=content, close_label="Close")


