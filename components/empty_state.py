from __future__ import annotations

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import BooleanProperty, ObjectProperty, StringProperty
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.label import MDIcon, MDLabel

from components.app_button import AppButton
from theme import TEXT_PRIMARY, TEXT_SECONDARY


class EmptyState(MDBoxLayout):
    """Reusable empty-state illustration, copy, and optional CTA."""

    icon = StringProperty("inbox-outline")
    title = StringProperty("Nothing here yet")
    message = StringProperty("We will show items here once they arrive.")
    action_text = StringProperty("")
    action_variant = StringProperty("primary")
    show_action = BooleanProperty(True)
    action_callback = ObjectProperty(None, allownone=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.size_hint_y = None
        self.adaptive_height = True
        self.padding = [dp(16), dp(16), dp(16), dp(16)]
        self.spacing = dp(10)

        self._icon = MDIcon(
            icon=self.icon,
            theme_text_color="Custom",
            text_color=list(TEXT_SECONDARY),
            font_size="44sp",
            halign="center",
            size_hint_y=None,
            height=dp(54),
        )
        self._title = MDLabel(
            text=self.title,
            theme_text_color="Custom",
            text_color=list(TEXT_PRIMARY),
            bold=True,
            halign="center",
            adaptive_height=True,
        )
        self._message = MDLabel(
            text=self.message,
            theme_text_color="Custom",
            text_color=list(TEXT_SECONDARY),
            halign="center",
            adaptive_height=True,
        )
        self._action_wrap = MDBoxLayout(
            orientation="vertical",
            adaptive_height=True,
            size_hint_y=None,
            height=0,
            opacity=0,
        )
        self._action_button = AppButton(text="", variant=self.action_variant)
        self._action_button.bind(on_release=self._dispatch_action)
        self._action_wrap.add_widget(self._action_button)

        self.add_widget(self._icon)
        self.add_widget(self._title)
        self.add_widget(self._message)
        self.add_widget(self._action_wrap)
        self.bind(icon=self._sync, title=self._sync, message=self._sync, action_text=self._sync, action_variant=self._sync, show_action=self._sync)
        Clock.schedule_once(self._sync, 0)

    def _sync(self, *_args):
        self._icon.icon = str(self.icon or "inbox-outline")
        self._title.text = str(self.title or "")
        self._message.text = str(self.message or "")

        action_text = str(self.action_text or "").strip()
        show_action = bool(self.show_action and action_text)
        self._action_button.text = action_text
        self._action_button.variant = str(self.action_variant or "primary")
        self._action_wrap.height = dp(52) if show_action else 0
        self._action_wrap.opacity = 1 if show_action else 0
        self._action_wrap.disabled = not show_action
        self.height = self.minimum_height

    def _dispatch_action(self, *_args):
        callback = self.action_callback
        if not callable(callback):
            return
        try:
            callback(self)
        except TypeError:
            callback()


try:
    from kivy.factory import Factory

    Factory.register("EmptyState", cls=EmptyState)
except Exception:
    pass
