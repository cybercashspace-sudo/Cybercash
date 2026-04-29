from __future__ import annotations

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.properties import BooleanProperty, NumericProperty
from kivy.uix.scrollview import ScrollView
from kivymd.uix.screen import MDScreen

from core.bottom_nav import BottomNavBar  # noqa: F401


class ResponsiveScreen(MDScreen):
    """Adds a responsive max-width content container for ScrollView screens."""

    content_max_width = NumericProperty(460.0)
    content_max_width_tablet = NumericProperty(620.0)
    content_max_width_desktop = NumericProperty(720.0)
    layout_scale = NumericProperty(1.0)
    text_scale = NumericProperty(1.0)
    icon_scale = NumericProperty(1.0)
    compact_mode = BooleanProperty(False)
    tablet_mode = BooleanProperty(False)
    quick_action_cols = NumericProperty(4)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        Window.bind(size=self._on_window_resize)
        self._refresh_responsive_metrics()

    def on_kv_post(self, _base_widget):
        super().on_kv_post(_base_widget)
        Clock.schedule_once(lambda _dt: self._refresh_and_apply_layout(), 0)

    def on_size(self, *_args):
        Clock.schedule_once(lambda _dt: self._refresh_and_apply_layout(), 0)

    def _on_window_resize(self, *_args):
        Clock.schedule_once(lambda _dt: self._refresh_and_apply_layout(), 0)

    @staticmethod
    def _clamp(value: float, minimum: float, maximum: float) -> float:
        return max(minimum, min(maximum, float(value)))

    def _refresh_responsive_metrics(self) -> None:
        width, height = Window.size
        base_width = 390.0
        base_height = 844.0
        width_ratio = float(width or base_width) / base_width
        height_ratio = float(height or base_height) / base_height
        compact_penalty = 0.92 if width < 360 else 1.0
        layout = self._clamp((width_ratio * 0.68 + height_ratio * 0.32) * compact_penalty, 0.82, 1.12)
        text = self._clamp(layout * (0.98 if width < 360 else 1.0), 0.88, 1.08)
        icon = self._clamp(layout * 1.02, 0.90, 1.10)

        self.layout_scale = layout
        self.text_scale = text
        self.icon_scale = icon
        self.compact_mode = bool(width < 360)
        self.tablet_mode = bool(width >= 700)
        self.quick_action_cols = 2 if width < 360 else 4

    def _refresh_and_apply_layout(self) -> None:
        self._refresh_responsive_metrics()
        self._apply_responsive_layout()

    @staticmethod
    def _scroll_content(scroll: ScrollView):
        if not scroll.children:
            return None
        # Kivy's ScrollView keeps a single content child.
        return scroll.children[0]

    def _target_content_width(self, available_width: float) -> float:
        window_width = float(Window.size[0] or available_width or 0.0)
        if window_width >= 1440:
            max_width = dp(self.content_max_width_desktop)
        elif window_width >= 900:
            max_width = dp(self.content_max_width_tablet)
        else:
            max_width = dp(self.content_max_width)
        if available_width <= 0:
            return max_width
        return min(float(available_width), float(max_width))

    def _apply_responsive_layout(self):
        for widget in self.walk(restrict=True):
            if not isinstance(widget, ScrollView):
                continue
            content = self._scroll_content(widget)
            if content is None:
                continue

            available_width = float(widget.width or self.width or Window.size[0] or 0.0)
            target_width = self._target_content_width(available_width)

            try:
                content.size_hint_x = None
                content.width = target_width
                pos_hint = dict(getattr(content, "pos_hint", {}) or {})
                pos_hint["center_x"] = 0.5
                content.pos_hint = pos_hint
            except Exception:
                # Keep UI usable even if a specific widget rejects width hints.
                continue
