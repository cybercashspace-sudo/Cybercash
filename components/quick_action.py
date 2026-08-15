from __future__ import annotations

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import BooleanProperty, ListProperty, StringProperty
from kivy.uix.behaviors import ButtonBehavior
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel

from animations.effects import AnimationManager
from core.feedback_engine import tap_feedback
from theme import CARD_RADIUS, PRIMARY, SURFACE, TEXT_PRIMARY, TEXT_SECONDARY


class QuickAction(ButtonBehavior, MDCard):
    """Reusable tappable action tile for dashboard shortcuts."""

    icon = StringProperty("circle")
    title = StringProperty("")
    subtitle = StringProperty("")
    target = StringProperty("")
    auto_navigate = BooleanProperty(False)
    background_color = ListProperty(list(SURFACE))
    icon_color = ListProperty(list(PRIMARY))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint_y = None
        self.height = dp(104)
        self.radius = list(CARD_RADIUS)
        self.elevation = 0
        self.md_bg_color = list(self.background_color)
        self._content = MDBoxLayout(orientation="vertical", padding=[dp(12), dp(12), dp(12), dp(12)], spacing=dp(8))
        self._icon_card = MDCard(size_hint=(None, None), size=(dp(42), dp(42)), radius=[dp(14), dp(14), dp(14), dp(14)], md_bg_color=list(self.icon_color), elevation=0)
        self._icon_label = MDLabel(text=" ", halign="center", theme_text_color="Custom", text_color=[0, 0, 0, 1], bold=True)
        self._title_label = MDLabel(theme_text_color="Custom", text_color=list(TEXT_PRIMARY), bold=True, font_size="14sp", adaptive_height=True)
        self._subtitle_label = MDLabel(theme_text_color="Custom", text_color=list(TEXT_SECONDARY), font_size="11sp", adaptive_height=True)
        self._icon_card.add_widget(self._icon_label)
        self._content.add_widget(self._icon_card)
        self._content.add_widget(self._title_label)
        self._content.add_widget(self._subtitle_label)
        self.add_widget(self._content)
        self.bind(
            icon=self._sync,
            title=self._sync,
            subtitle=self._sync,
            background_color=self._sync,
            icon_color=self._sync,
        )
        self.bind(on_press=self._animate_press, on_release=self._handle_release)
        Clock.schedule_once(self._sync, 0)

    def _sync(self, *_args):
        self.md_bg_color = list(self.background_color or SURFACE)
        self._icon_card.md_bg_color = list(self.icon_color or PRIMARY)
        self._icon_label.text = str(self.icon or "")[:1].upper() or " "
        self._title_label.text = str(self.title or "")
        self._subtitle_label.text = str(self.subtitle or "")

    def _animate_press(self, *_args):
        AnimationManager.pulse(self, shrink=0.96, duration=0.08)

    def _handle_release(self, *_args):
        tap_feedback()
        if not self.auto_navigate or not self.target:
            return
        app = MDApp.get_running_app()
        if app is not None and hasattr(app, "go_to_screen"):
            app.go_to_screen(self.target, fallback=getattr(getattr(app, "root", None), "current", "home") or "home")


try:
    from kivy.factory import Factory

    Factory.register("QuickAction", cls=QuickAction)
except Exception:
    pass

