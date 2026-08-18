from __future__ import annotations

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import BooleanProperty, ListProperty, NumericProperty, ObjectProperty, StringProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.widget import Widget
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDIcon, MDLabel

from core.animation_helpers import AnimationManager
from components.animated_card import AnimatedCard
from components.notification_badge import NotificationBadge
from core.feedback_engine import tap_feedback
from theme import CARD_RADIUS, PRIMARY, SURFACE, TEXT_PRIMARY, TEXT_SECONDARY


class QuickAction(ButtonBehavior, AnimatedCard):
    """Reusable tappable action tile for dashboard shortcuts."""

    icon = StringProperty("circle")
    text = StringProperty("")
    title = StringProperty("")
    subtitle = StringProperty("")
    target = StringProperty("")
    callback = ObjectProperty(None, allownone=True)
    auto_navigate = BooleanProperty(False)
    enabled = BooleanProperty(True)
    loading = BooleanProperty(False)
    badge_count = NumericProperty(0)
    loading_text = StringProperty("Loading...")
    background_color = ListProperty(list(SURFACE))
    icon_color = ListProperty(list(PRIMARY))
    badge_color = ListProperty(list(PRIMARY))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint_y = None
        self.height = dp(108)
        self.radius = list(CARD_RADIUS)
        self.elevation = 0
        self.border_width = 1.0
        self.border_color = [1, 1, 1, 0.08]
        self.gradient_start = list(self.background_color or SURFACE)
        self.gradient_end = list(self.background_color or SURFACE)

        self._root = MDBoxLayout(
            orientation="horizontal",
            spacing=dp(12),
            padding=[dp(14), dp(12), dp(14), dp(12)],
            adaptive_height=True,
        )
        self._icon_layer = FloatLayout(size_hint=(None, None), size=(dp(48), dp(48)))
        self._icon_card = MDCard(
            size_hint=(None, None),
            size=(dp(48), dp(48)),
            radius=[dp(16), dp(16), dp(16), dp(16)],
            md_bg_color=list(self.icon_color or PRIMARY),
            line_color=[1, 1, 1, 0.08],
            elevation=0,
            pos_hint={"center_x": 0.5, "center_y": 0.5},
        )
        self._icon = MDIcon(
            icon=self.icon,
            theme_text_color="Custom",
            text_color=[0, 0, 0, 1],
            font_size="24sp",
            pos_hint={"center_x": 0.5, "center_y": 0.5},
        )
        self._badge = NotificationBadge(count=self.badge_count)
        self._badge.size = (dp(18), dp(18))
        self._badge.pos_hint = {"right": 1, "top": 1}
        self._badge.opacity = 0
        self._text_stack = MDBoxLayout(orientation="vertical", spacing=dp(4), adaptive_height=True)
        self._title_label = MDLabel(
            text="",
            theme_text_color="Custom",
            text_color=list(TEXT_PRIMARY),
            bold=True,
            font_size="14sp",
            adaptive_height=True,
            shorten=True,
            shorten_from="right",
        )
        self._subtitle_label = MDLabel(
            text="",
            theme_text_color="Custom",
            text_color=list(TEXT_SECONDARY),
            font_size="11sp",
            adaptive_height=True,
            shorten=True,
            shorten_from="right",
        )

        self._icon_layer.add_widget(self._icon_card)
        self._icon_layer.add_widget(self._icon)
        self._icon_layer.add_widget(self._badge)
        self._text_stack.add_widget(self._title_label)
        self._text_stack.add_widget(self._subtitle_label)
        self._root.add_widget(self._icon_layer)
        self._root.add_widget(self._text_stack)
        self._root.add_widget(Widget())
        self.add_widget(self._root)

        self.bind(
            icon=self._sync,
            text=self._sync,
            title=self._sync,
            subtitle=self._sync,
            background_color=self._sync,
            icon_color=self._sync,
            badge_color=self._sync,
            badge_count=self._sync,
            enabled=self._sync,
            loading=self._sync,
        )
        self.bind(on_press=self._animate_press, on_release=self._handle_release)
        Clock.schedule_once(self._sync, 0)

    def _sync(self, *_args):
        display_title = str(self.title or self.text or "").strip()
        display_subtitle = str(self.subtitle or "").strip()
        is_loading = bool(self.loading)
        is_enabled = bool(self.enabled and not is_loading)

        self.gradient_start = list(self.background_color or SURFACE)
        self.gradient_end = list(self.background_color or SURFACE)
        self.border_color = [1, 1, 1, 0.08] if is_enabled else [1, 1, 1, 0.04]
        self._icon_card.md_bg_color = list(self.icon_color or PRIMARY)
        self._icon.text_color = [0, 0, 0, 1]
        self._icon.icon = "progress-clock" if is_loading else str(self.icon or "circle")
        self._title_label.text = display_title or ("Loading..." if is_loading else "")
        self._subtitle_label.text = str(self.loading_text if is_loading else display_subtitle or "")
        self._subtitle_label.text_color = list(TEXT_SECONDARY if is_enabled else [0.65, 0.65, 0.65, 1])
        self._badge.md_bg_color = list(self.badge_color or PRIMARY)
        self._badge.count = int(self.badge_count or 0)
        self._badge.opacity = 1 if int(self.badge_count or 0) > 0 else 0
        self.disabled = not is_enabled
        self.opacity = 0.72 if is_loading else 1.0

    def _animate_press(self, *_args):
        if self.loading or not self.enabled:
            return
        AnimationManager.pulse(self, shrink=0.96, duration=0.08)

    def _handle_release(self, *_args):
        if self.loading or not self.enabled:
            return
        tap_feedback()

        callback = self.callback
        if callable(callback):
            try:
                callback(self)
            except TypeError:
                callback()

        if self.auto_navigate and self.target:
            self._navigate(self.target)

    def _navigate(self, target: str) -> None:
        app = MDApp.get_running_app()
        if app is None:
            return

        if hasattr(app, "go_to_screen"):
            app.go_to_screen(target, fallback=getattr(getattr(app, "root", None), "current", "home") or "home")
            return

        if hasattr(app, "go_to"):
            app.go_to(target)


try:
    from kivy.factory import Factory

    Factory.register("QuickAction", cls=QuickAction)
except Exception:
    pass
