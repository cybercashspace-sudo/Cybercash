from __future__ import annotations

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp
from kivy.properties import BooleanProperty, ListProperty, NumericProperty, StringProperty
from kivy.uix.relativelayout import RelativeLayout

from core.auth_assets import auth_asset_path
from core.kivymd_compat import register_legacy_button_aliases
from theme import GLASS_BG, GLASS_BORDER, PRIMARY, PRIMARY_DARK, TEXT_PRIMARY, TEXT_SECONDARY

register_legacy_button_aliases()

from kivymd.uix.card import MDCard  # noqa: E402
from kivymd.uix.fitimage import FitImage  # noqa: E402
from kivymd.uix.label import MDIcon, MDLabel  # noqa: E402


class GlassCard(MDCard):
    """
    Glassmorphism card used throughout CYBER CASH.
    """

    corner_radius = NumericProperty(dp(28))
    shadow_opacity = NumericProperty(0.22)
    shadow_offset = NumericProperty(dp(3))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.radius = [dp(28)]
        self.elevation = 0
        self.md_bg_color = GLASS_BG
        self.line_color = GLASS_BORDER
        Clock.schedule_once(self._bind_shadow, 0)

    def _bind_shadow(self, *_):
        self.bind(pos=self._update_canvas, size=self._update_canvas)
        self._update_canvas()

    def _update_canvas(self, *_):
        self.canvas.before.clear()

        with self.canvas.before:
            Color(0, 0, 0, self.shadow_opacity)
            RoundedRectangle(
                pos=(self.x, self.y - self.shadow_offset),
                size=self.size,
                radius=[self.corner_radius],
            )


class GoldButton(MDCard):
    """
    Primary gold action button that matches the auth screen artwork.
    """

    text = StringProperty("Login")
    busy_text = StringProperty("Loading...")
    loading = BooleanProperty(False)
    arrow_source = StringProperty(auth_asset_path("12_login_arrow_circle.png"))
    base_color = ListProperty(PRIMARY)
    pressed_color = ListProperty(PRIMARY_DARK)
    text_color_value = ListProperty([0, 0, 0, 1])

    def __init__(self, **kwargs):
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(68))
        super().__init__(**kwargs)
        self.radius = [dp(28)]
        self.elevation = 0
        self.line_color = (0, 0, 0, 0)
        self.md_bg_color = list(self.base_color)

        self._content = RelativeLayout(size_hint=(1, 1))
        self._label = MDLabel(
            text=self.text,
            halign="center",
            valign="middle",
            bold=True,
            font_style="Title",
            theme_text_color="Custom",
            text_color=list(self.text_color_value),
            pos_hint={"center_x": 0.5, "center_y": 0.5},
        )
        self._arrow = FitImage(
            source=self.arrow_source,
            size_hint=(None, None),
            size=(dp(46), dp(46)),
            pos_hint={"center_y": 0.5, "right": 0.96},
            opacity=1,
        )

        self._content.add_widget(self._label)
        self._content.add_widget(self._arrow)
        self.add_widget(self._content)
        self.bind(
            text=self._sync_text,
            busy_text=self._sync_text,
            arrow_source=self._sync_arrow,
            loading=self._sync_loading,
        )
        self.bind(on_press=self._press, on_release=self._release)
        self._sync_text()
        self._sync_arrow()
        self._sync_loading()

    def _sync_text(self, *_):
        self._label.text = self.busy_text if self.loading else self.text

    def _sync_arrow(self, *_):
        self._arrow.source = self.arrow_source

    def _sync_loading(self, *_):
        self.disabled = bool(self.loading)
        self.opacity = 0.9 if self.loading else 1
        self._sync_text()

    def _press(self, *_):
        Animation(md_bg_color=list(self.pressed_color), d=0.08).start(self)

    def _release(self, *_):
        Animation(md_bg_color=list(self.base_color), d=0.12).start(self)


class SocialButton(MDCard):
    """
    Social login tile with the exact auth assets.
    """

    text = StringProperty("Google")
    source = StringProperty("")
    base_color = ListProperty([0.12, 0.12, 0.12, 1])
    pressed_color = ListProperty([0.18, 0.18, 0.18, 1])
    label_color = ListProperty(TEXT_PRIMARY)
    border_color = ListProperty(GLASS_BORDER)

    def __init__(self, **kwargs):
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(130))
        super().__init__(**kwargs)
        self.radius = [dp(18)]
        self.elevation = 0
        self.line_color = list(self.border_color)
        self.md_bg_color = list(self.base_color)

        self._content = RelativeLayout(size_hint=(1, 1))
        self._icon = FitImage(
            source=self.source,
            size_hint=(None, None),
            size=(dp(42), dp(42)),
            pos_hint={"center_x": 0.5, "top": 0.82},
            opacity=1,
        )
        self._label = MDLabel(
            text=self.text,
            halign="center",
            valign="middle",
            theme_text_color="Custom",
            text_color=list(self.label_color),
            font_style="Body",
            bold=False,
            pos_hint={"center_x": 0.5, "y": 0.07},
        )

        self._content.add_widget(self._icon)
        self._content.add_widget(self._label)
        self.add_widget(self._content)
        self.bind(text=self._sync_text, source=self._sync_source)
        self.bind(on_press=self._press, on_release=self._release)
        self._sync_text()
        self._sync_source()

    def _sync_text(self, *_):
        self._label.text = self.text

    def _sync_source(self, *_):
        self._icon.source = self.source

    def _press(self, *_):
        Animation(md_bg_color=list(self.pressed_color), d=0.08).start(self)

    def _release(self, *_):
        Animation(md_bg_color=list(self.base_color), d=0.12).start(self)


class PasswordToggleButton(ButtonBehavior, RelativeLayout):
    """
    Toggle button that uses the exact eye-off asset for the default state.
    """

    visible = BooleanProperty(False)
    hidden_source = StringProperty(auth_asset_path("10_eye_off_icon.png"))
    visible_icon = StringProperty("eye")
    icon_color = ListProperty(TEXT_SECONDARY)

    def __init__(self, **kwargs):
        kwargs.setdefault("size_hint", (None, None))
        kwargs.setdefault("size", (dp(32), dp(32)))
        super().__init__(**kwargs)

        self._hidden = FitImage(
            source=self.hidden_source,
            size_hint=(None, None),
            size=(dp(24), dp(24)),
            pos_hint={"center_x": 0.5, "center_y": 0.5},
            opacity=1,
        )
        self._visible = MDIcon(
            icon=self.visible_icon,
            font_size="24sp",
            theme_text_color="Custom",
            text_color=list(self.icon_color),
            pos_hint={"center_x": 0.5, "center_y": 0.5},
            opacity=0,
        )
        self.add_widget(self._hidden)
        self.add_widget(self._visible)
        self.bind(visible=self._sync_state, hidden_source=self._sync_state, visible_icon=self._sync_state)
        self._sync_state()

    def _sync_state(self, *_):
        self._hidden.opacity = 0 if self.visible else 1
        self._visible.opacity = 1 if self.visible else 0
        self._hidden.source = self.hidden_source
        self._visible.icon = self.visible_icon


class RememberCheckButton(ButtonBehavior, RelativeLayout):
    """
    Checkbox-style button that uses the exact checked asset by default.
    """

    checked = BooleanProperty(True)
    checked_source = StringProperty(auth_asset_path("11_remember_check_icon.png"))
    unchecked_icon = StringProperty("checkbox-blank-outline")
    checked_icon_color = ListProperty(PRIMARY)
    unchecked_icon_color = ListProperty(TEXT_SECONDARY)

    def __init__(self, **kwargs):
        kwargs.setdefault("size_hint", (None, None))
        kwargs.setdefault("size", (dp(24), dp(24)))
        super().__init__(**kwargs)

        self._checked = FitImage(
            source=self.checked_source,
            size_hint=(None, None),
            size=(dp(24), dp(24)),
            pos_hint={"center_x": 0.5, "center_y": 0.5},
            opacity=1,
        )
        self._unchecked = MDIcon(
            icon=self.unchecked_icon,
            font_size="20sp",
            theme_text_color="Custom",
            text_color=list(self.unchecked_icon_color),
            pos_hint={"center_x": 0.5, "center_y": 0.5},
            opacity=0,
        )
        self.add_widget(self._checked)
        self.add_widget(self._unchecked)
        self.bind(
            checked=self._sync_state,
            checked_source=self._sync_state,
            unchecked_icon=self._sync_state,
        )
        self._sync_state()

    def _sync_state(self, *_):
        self._checked.opacity = 1 if self.checked else 0
        self._unchecked.opacity = 0 if self.checked else 1
        self._checked.source = self.checked_source
        self._unchecked.icon = self.unchecked_icon


__all__ = [
    "GlassCard",
    "GoldButton",
    "PasswordToggleButton",
    "RememberCheckButton",
    "SocialButton",
]
