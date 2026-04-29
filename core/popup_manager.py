from __future__ import annotations

import re
from typing import Callable, Optional

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView

from core.message_sanitizer import extract_backend_message


_DIALOG_BG_COLOR = (0.08, 0.10, 0.14, 0.98)
_ACCENT_GOLD = (0.94, 0.79, 0.46, 1)
_ACCENT_GOLD_SOFT = (0.93, 0.77, 0.39, 1)
_ACCENT_DARK_TEXT = (0.07, 0.08, 0.10, 1)
_TEXT_LIGHT = (0.92, 0.93, 0.95, 1)


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _friendly_title(title: str) -> str:
    cleaned = _normalize_whitespace(title)
    return cleaned if cleaned else "Notice"


def _friendly_message(message: str) -> str:
    return extract_backend_message(message, fallback="Please review this message.")


def _clear_active_dialog(owner, dialog_obj: Popup | None = None) -> None:
    current = getattr(owner, "_active_dialog", None)
    if dialog_obj is None or current is dialog_obj:
        owner._active_dialog = None


def _dismiss_dialog(owner) -> None:
    dialog = getattr(owner, "_active_dialog", None)
    if dialog is not None:
        try:
            dialog.dismiss()
        except Exception:
            pass
    _clear_active_dialog(owner)


def _make_text_label(text: str) -> Label:
    return Label(
        text=str(text or ""),
        color=_TEXT_LIGHT,
        halign="left",
        valign="top",
        font_size="15sp",
        text_size=(dp(300), None),
        size_hint_y=None,
    )


def _resize_label_text(label: Label):
    label.bind(
        width=lambda _i, w: setattr(label, "text_size", (max(1, w), None)),
        texture_size=lambda _i, ts: setattr(label, "height", max(dp(38), ts[1] + dp(4))),
    )


def _make_popup(title: str, content, *, auto_dismiss: bool = False, height: float = 320) -> Popup:
    popup = Popup(
        title=_friendly_title(title),
        content=content,
        auto_dismiss=bool(auto_dismiss),
        size_hint=(0.9, None),
        height=dp(height),
        separator_color=_ACCENT_GOLD,
        title_color=_ACCENT_GOLD,
        title_size="18sp",
        background_color=_DIALOG_BG_COLOR,
    )
    return popup


def _make_button(
    text: str,
    on_release: Callable,
    *,
    background_color=(0.20, 0.24, 0.31, 1),
    color=_TEXT_LIGHT,
) -> Button:
    btn = Button(
        text=str(text or "Close"),
        size_hint_y=None,
        height=dp(44),
        background_normal="",
        background_down="",
        background_color=background_color,
        color=color,
        font_size="15sp",
        bold=True,
    )
    btn.bind(on_release=on_release)
    return btn


def show_message_dialog(
    owner,
    *,
    title: str,
    message: str,
    close_label: str = "Close",
    on_close: Optional[Callable[[], None]] = None,
) -> None:
    _dismiss_dialog(owner)

    container = BoxLayout(
        orientation="vertical",
        spacing=dp(12),
        padding=[dp(14), dp(14), dp(14), dp(14)],
    )
    message_label = _make_text_label(_friendly_message(message))
    _resize_label_text(message_label)

    scroll = ScrollView(do_scroll_x=False, bar_width=dp(3))
    message_box = BoxLayout(orientation="vertical", size_hint_y=None, padding=[0, 0, dp(4), 0])
    message_box.bind(minimum_height=message_box.setter("height"))
    message_box.add_widget(message_label)
    scroll.add_widget(message_box)

    def _on_close(*_args):
        _dismiss_dialog(owner)
        if on_close:
            on_close()

    actions = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(46), spacing=dp(10))
    actions.add_widget(
        _make_button(
            close_label,
            _on_close,
            background_color=_ACCENT_GOLD_SOFT,
            color=_ACCENT_DARK_TEXT,
        )
    )

    container.add_widget(scroll)
    container.add_widget(actions)

    popup = _make_popup(title, container, auto_dismiss=False, height=360)
    popup.bind(on_dismiss=lambda *_args: _clear_active_dialog(owner, popup))
    owner._active_dialog = popup
    popup.open()


def show_confirm_dialog(
    owner,
    *,
    title: str,
    message: str,
    on_confirm: Callable[[], None],
    confirm_label: str = "Confirm",
    cancel_label: str = "Cancel",
) -> None:
    _dismiss_dialog(owner)

    container = BoxLayout(
        orientation="vertical",
        spacing=dp(12),
        padding=[dp(14), dp(14), dp(14), dp(14)],
    )
    message_label = _make_text_label(_friendly_message(message))
    _resize_label_text(message_label)

    scroll = ScrollView(do_scroll_x=False, bar_width=dp(3))
    message_box = BoxLayout(orientation="vertical", size_hint_y=None, padding=[0, 0, dp(4), 0])
    message_box.bind(minimum_height=message_box.setter("height"))
    message_box.add_widget(message_label)
    scroll.add_widget(message_box)

    def _on_cancel(*_args):
        _dismiss_dialog(owner)

    def _on_confirm(*_args):
        _dismiss_dialog(owner)
        on_confirm()

    actions = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(46), spacing=dp(10))
    actions.add_widget(_make_button(cancel_label or "Cancel", _on_cancel))
    actions.add_widget(
        _make_button(
            confirm_label or "Confirm",
            _on_confirm,
            background_color=_ACCENT_GOLD_SOFT,
            color=_ACCENT_DARK_TEXT,
        )
    )

    container.add_widget(scroll)
    container.add_widget(actions)

    popup = _make_popup(title or "Confirm Action", container, auto_dismiss=False, height=360)
    popup.bind(on_dismiss=lambda *_args: _clear_active_dialog(owner, popup))
    owner._active_dialog = popup
    popup.open()


def show_custom_dialog(
    owner,
    *,
    title: str,
    content_cls,
    close_label: str = "Close",
    on_close: Optional[Callable[[], None]] = None,
    auto_dismiss: bool = True,
):
    _dismiss_dialog(owner)

    container = BoxLayout(
        orientation="vertical",
        spacing=dp(12),
        padding=[dp(12), dp(12), dp(12), dp(12)],
    )

    content_holder = ScrollView(do_scroll_x=False, bar_width=dp(3))
    content_wrapper = BoxLayout(orientation="vertical", size_hint_y=None)
    content_wrapper.bind(minimum_height=content_wrapper.setter("height"))
    if hasattr(content_cls, "size_hint_y"):
        try:
            content_cls.size_hint_y = None if content_cls.size_hint_y is None else content_cls.size_hint_y
        except Exception:
            pass
    content_wrapper.add_widget(content_cls)
    content_holder.add_widget(content_wrapper)

    def _on_close(*_args):
        _dismiss_dialog(owner)
        if on_close:
            on_close()

    actions = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(46), spacing=dp(10))
    actions.add_widget(
        _make_button(
            close_label,
            _on_close,
            background_color=_ACCENT_GOLD_SOFT,
            color=_ACCENT_DARK_TEXT,
        )
    )

    container.add_widget(content_holder)
    container.add_widget(actions)

    popup = _make_popup(title, container, auto_dismiss=bool(auto_dismiss), height=430)
    popup.bind(on_dismiss=lambda *_args: _clear_active_dialog(owner, popup))
    owner._active_dialog = popup
    popup.open()
    return popup
