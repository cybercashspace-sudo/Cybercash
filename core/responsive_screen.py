from __future__ import annotations

import threading
import time

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.graphics import Color, RoundedRectangle
from kivy.properties import BooleanProperty, NumericProperty
from kivy.uix.scrollview import ScrollView
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivymd.uix.screen import MDScreen

from core.bottom_nav import BottomNavBar  # noqa: F401
from core.pull_refresh import PullToRefreshMixin
from core.ui_effects import FintechSpinner
from core.navigation import navigate_back


class _RequestLoadingOverlay(FloatLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.owner_screen = None
        self.size_hint = (1, 1)
        self.opacity = 0
        self.disabled = True
        with self.canvas.before:
            self._shade = Color(0.02, 0.03, 0.05, 0.0)
            self._shade_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(16)])
        self.bind(pos=self._update_shade, size=self._update_shade)

        content = BoxLayout(
            orientation="vertical",
            size_hint=(None, None),
            size=(dp(112), dp(96)),
            spacing=dp(8),
            padding=dp(12),
            pos_hint={"center_x": 0.5, "center_y": 0.5},
        )
        with content.canvas.before:
            Color(0.08, 0.10, 0.14, 0.98)
            self._card = RoundedRectangle(pos=content.pos, size=content.size, radius=[dp(16)])
        content.bind(pos=lambda widget, _value: setattr(self._card, "pos", widget.pos))
        content.bind(size=lambda widget, _value: setattr(self._card, "size", widget.size))
        self.spinner = FintechSpinner(
            size_hint=(None, None),
            size=(dp(30), dp(30)),
            active=False,
            color=[0.94, 0.79, 0.46, 1],
            pos_hint={"center_x": 0.5},
        )
        content.add_widget(self.spinner)
        content.add_widget(Label(text="Please wait", color=(0.95, 0.95, 0.95, 1), font_size="13sp"))
        self.add_widget(content)

    def _update_shade(self, *_args):
        self._shade_rect.pos = self.pos
        self._shade_rect.size = self.size

    def set_active(self, active: bool):
        self.opacity = 1 if active else 0
        self.disabled = not active
        self._shade.rgba = (0.02, 0.03, 0.05, 0.38 if active else 0.0)
        self.spinner.active = bool(active)

    def on_touch_down(self, touch):
        if (
            self.opacity
            and bool(getattr(self.owner_screen, "block_interaction_while_loading", True))
            and self.collide_point(*touch.pos)
        ):
            return True
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if (
            self.opacity
            and bool(getattr(self.owner_screen, "block_interaction_while_loading", True))
            and self.collide_point(*touch.pos)
        ):
            return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if (
            self.opacity
            and bool(getattr(self.owner_screen, "block_interaction_while_loading", True))
            and self.collide_point(*touch.pos)
        ):
            return True
        return super().on_touch_up(touch)


def install_request_overlay(screen, property_names=()):
    if getattr(screen, "_request_overlay", None) is not None:
        return screen._request_overlay
    overlay = _RequestLoadingOverlay()
    overlay.owner_screen = screen
    screen._request_overlay = overlay
    screen.add_widget(overlay)

    def sync_overlay(*_args):
        active = bool(getattr(screen, "screen_loading", False))
        active = active or any(bool(getattr(screen, name, False)) for name in property_names)
        overlay.set_active(active)

    available = screen.properties() if callable(getattr(screen, "properties", None)) else {}
    for name in property_names:
        if name in available:
            screen.bind(**{name: sync_overlay})
    if "screen_loading" in available:
        screen.bind(screen_loading=sync_overlay)
    sync_overlay()
    return overlay


class ResponsiveScreen(PullToRefreshMixin, MDScreen):
    """Adds a responsive max-width content container for ScrollView screens."""

    _SWIPE_BACK_KEY = "_cybercash_screen_swipe_start"

    content_max_width = NumericProperty(460.0)
    content_max_width_tablet = NumericProperty(620.0)
    content_max_width_desktop = NumericProperty(720.0)
    layout_scale = NumericProperty(1.0)
    text_scale = NumericProperty(1.0)
    icon_scale = NumericProperty(1.0)
    compact_mode = BooleanProperty(False)
    tablet_mode = BooleanProperty(False)
    quick_action_cols = NumericProperty(4)
    screen_loading = BooleanProperty(False)
    _REQUEST_BUSY_PROPERTIES = (
        "loading", "processing", "deposit_busy", "transfer_busy", "escrow_busy",
        "loan_refresh_busy", "loan_submit_busy", "repayment_busy", "card_refresh_busy",
        "card_request_busy", "card_action_busy", "email_change_loading", "dashboard_syncing",
    )

    def __init__(self, **kwargs):
        self._layout_refresh_event = None
        self._window_bound = False
        self._request_activity_count = 0
        self._request_activity_lock = threading.RLock()
        self._request_activity_visible_until = 0.0
        self._request_overlay_hide_event = None
        self._request_overlay = None
        super().__init__(**kwargs)
        # ScreenManager retains visited screens for fast navigation. Keep the
        # global Window binding active only while this screen is on-screen.
        self.bind(on_pre_enter=self._on_screen_pre_enter, on_leave=self._on_screen_leave)
        self._refresh_responsive_metrics()
        self._schedule_layout_refresh()

    def _on_screen_pre_enter(self, *_args) -> None:
        self._bind_window_resize()
        self._schedule_layout_refresh()

    def _on_screen_leave(self, *_args) -> None:
        self._cancel_layout_refresh()
        self._unbind_window_resize()

    def _bind_window_resize(self) -> None:
        if self._window_bound:
            return
        Window.bind(size=self._on_window_resize)
        self._window_bound = True

    def _unbind_window_resize(self) -> None:
        if not self._window_bound:
            return
        try:
            Window.unbind(size=self._on_window_resize)
        except Exception:
            pass
        finally:
            self._window_bound = False

    def _cancel_layout_refresh(self) -> None:
        event = getattr(self, "_layout_refresh_event", None)
        if event is None:
            return
        try:
            event.cancel()
        except Exception:
            pass
        finally:
            self._layout_refresh_event = None

    def _schedule_layout_refresh(self, delay: float = 0) -> None:
        self._cancel_layout_refresh()
        self._layout_refresh_event = Clock.schedule_once(lambda _dt: self._refresh_and_apply_layout(), delay)

    def on_kv_post(self, _base_widget):
        super().on_kv_post(_base_widget)
        self._install_request_overlay()
        self._schedule_layout_refresh()

    def _install_request_overlay(self):
        if self._request_overlay is not None:
            return
        install_request_overlay(self, self._REQUEST_BUSY_PROPERTIES)
        self.bind(screen_loading=lambda _instance, _value: self._sync_request_overlay())
        self._sync_request_overlay()

    def _sync_request_overlay(self, *_args):
        with self._request_activity_lock:
            request_active = self._request_activity_count > 0
            visible_until = self._request_activity_visible_until
        local_active = any(bool(getattr(self, name, False)) for name in self._REQUEST_BUSY_PROPERTIES)
        active = bool(request_active or local_active or time.monotonic() < visible_until)
        self.screen_loading = active
        if active:
            event = self._request_overlay_hide_event
            if event is not None:
                event.cancel()
                self._request_overlay_hide_event = None
        elif visible_until > time.monotonic():
            self._schedule_request_overlay_sync(visible_until - time.monotonic())

    def _schedule_request_overlay_sync(self, delay=0.0):
        event = self._request_overlay_hide_event
        if event is not None:
            event.cancel()
        self._request_overlay_hide_event = Clock.schedule_once(self._finish_request_overlay_sync, max(0.0, delay))

    def _finish_request_overlay_sync(self, _dt):
        self._request_overlay_hide_event = None
        self._sync_request_overlay()

    def _begin_request_activity(self):
        with self._request_activity_lock:
            self._request_activity_count += 1
            self._request_activity_visible_until = max(
                self._request_activity_visible_until,
                time.monotonic() + 0.14,
            )
        if threading.current_thread() is threading.main_thread():
            self._sync_request_overlay()
        else:
            with self._request_activity_lock:
                delay = max(0.0, self._request_activity_visible_until - time.monotonic())
            Clock.schedule_once(lambda _dt: self._sync_request_overlay())
            if delay:
                Clock.schedule_once(lambda _dt: self._sync_request_overlay(), delay)

    def _end_request_activity(self):
        with self._request_activity_lock:
            self._request_activity_count = max(0, self._request_activity_count - 1)
        if threading.current_thread() is threading.main_thread():
            self._sync_request_overlay()
        else:
            Clock.schedule_once(lambda _dt: self._sync_request_overlay())

    def go_back(self):
        return navigate_back(self)

    def on_size(self, *_args):
        if self._is_screen_active():
            self._schedule_layout_refresh()

    def on_parent(self, *_args):
        parent = getattr(self, "parent", None)
        if parent is None:
            self._cancel_layout_refresh()
            self._unbind_window_resize()
        else:
            self._schedule_layout_refresh()
        parent_on_parent = getattr(super(), "on_parent", None)
        if callable(parent_on_parent):
            return parent_on_parent(*_args)

    def _is_screen_active(self) -> bool:
        manager = getattr(self, "manager", None)
        if manager is None:
            return False
        return getattr(manager, "current_screen", None) is self

    def on_touch_down(self, touch):
        if self._is_screen_active() and touch.x <= self.x + dp(24):
            touch.ud[self._SWIPE_BACK_KEY] = (self, touch.x, touch.y)
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        origin = touch.ud.get(self._SWIPE_BACK_KEY)
        if origin and origin[0] is self:
            dx = touch.x - origin[1]
            dy = touch.y - origin[2]
            if dx >= dp(82) and dx > abs(dy) * 1.4:
                touch.ud.pop(self._SWIPE_BACK_KEY, None)
                if self._is_screen_active():
                    back = getattr(self, "go_back", None)
                    if callable(back):
                        back()
                        return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        touch.ud.pop(self._SWIPE_BACK_KEY, None)
        return super().on_touch_up(touch)

    def _on_window_resize(self, *_args):
        if not self._is_screen_active():
            return
        self._schedule_layout_refresh()

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
        self._layout_refresh_event = None
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

    def on_leave(self, *_args):
        self._cancel_layout_refresh()
        self._unbind_window_resize()
        parent_on_leave = getattr(super(), "on_leave", None)
        if callable(parent_on_leave):
            return parent_on_leave(*_args)
