from __future__ import annotations

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import BooleanProperty, NumericProperty, ObjectProperty, OptionProperty, StringProperty
from kivy.uix.floatlayout import FloatLayout
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDIcon, MDLabel

try:
    from kivymd.uix.spinner import MDSpinner
except Exception:  # pragma: no cover - fallback for older builds
    try:
        from kivymd.uix.progressspinner import MDSpinner
    except Exception:  # pragma: no cover - final fallback
        MDSpinner = None

from theme import ERROR, INFO, PRIMARY, SUCCESS, TEXT_PRIMARY, TEXT_SECONDARY, WARNING


class RefreshIndicator(MDBoxLayout):
    """Inline refresh status with pull/release/loading/complete states."""

    state = OptionProperty(
        "loading",
        options=("idle", "pull", "release", "loading", "complete", "error"),
    )
    active = BooleanProperty(True)
    text = StringProperty("Refreshing...")
    show_text = BooleanProperty(True)
    refresh_callback = ObjectProperty(None, allownone=True)
    auto_reset_delay = NumericProperty(1.2)
    refresh_duration = NumericProperty(0.18)
    pull_text = StringProperty("Pull to refresh")
    release_text = StringProperty("Release to refresh")
    loading_text = StringProperty("Refreshing...")
    complete_text = StringProperty("Refresh complete")
    error_text = StringProperty("Refresh failed")

    _STATE_CONFIG = {
        "idle": {"icon": "refresh", "color": TEXT_SECONDARY, "spinner": False},
        "pull": {"icon": "arrow-down-bold", "color": PRIMARY, "spinner": False},
        "release": {"icon": "arrow-up-bold", "color": WARNING, "spinner": False},
        "loading": {"icon": "progress-clock", "color": PRIMARY, "spinner": True},
        "complete": {"icon": "check-circle-outline", "color": SUCCESS, "spinner": False},
        "error": {"icon": "alert-circle-outline", "color": ERROR, "spinner": False},
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "horizontal"
        self.size_hint_y = None
        self.height = dp(24)
        self.spacing = dp(8)
        self._state = str(self.state or "loading")
        self._spinner = None
        self._icon = None
        self._indicator_shell = FloatLayout(size_hint=(None, None), size=(dp(18), dp(18)))
        self._label = MDLabel(
            text=self.text,
            theme_text_color="Custom",
            text_color=list(TEXT_SECONDARY),
            font_size="12sp",
            adaptive_height=True,
        )

        if MDSpinner is not None:
            self._spinner = MDSpinner(size_hint=(None, None), size=(dp(18), dp(18)), active=self.active)
            self._spinner.pos_hint = {"center_x": 0.5, "center_y": 0.5}
            self._indicator_shell.add_widget(self._spinner)

        self._icon = MDIcon(
            icon=self._STATE_CONFIG["loading"]["icon"],
            theme_text_color="Custom",
            text_color=list(PRIMARY),
            font_size="18sp",
            size_hint=(None, None),
            size=(dp(18), dp(18)),
            pos_hint={"center_x": 0.5, "center_y": 0.5},
        )
        self._indicator_shell.add_widget(self._icon)

        self.add_widget(self._indicator_shell)
        self.add_widget(self._label)
        self.bind(
            active=self._sync,
            text=self._sync,
            show_text=self._sync,
            state=self._sync,
            pull_text=self._sync,
            release_text=self._sync,
            loading_text=self._sync,
            complete_text=self._sync,
            error_text=self._sync,
        )
        Clock.schedule_once(self._sync, 0)

    def _state_text(self, state: str) -> str:
        current = str(state or "idle").strip().lower()
        if current == "pull":
            return str(self.pull_text or "Pull to refresh")
        if current == "release":
            return str(self.release_text or "Release to refresh")
        if current == "loading":
            return str(self.loading_text or "Refreshing...")
        if current == "complete":
            return str(self.complete_text or "Refresh complete")
        if current == "error":
            return str(self.error_text or "Refresh failed")
        return str(self.pull_text or "Pull to refresh")

    def _sync(self, *_args):
        state = str(self.state or "idle").strip().lower()
        if state not in self._STATE_CONFIG:
            state = "idle"
        config = self._STATE_CONFIG[state]

        self._state = state
        spinner_active = bool(config["spinner"] and self.active and state == "loading")
        if self._spinner is not None and hasattr(self._spinner, "active"):
            self._spinner.active = spinner_active
            self._spinner.opacity = 1 if spinner_active else 0

        self._icon.icon = str(config["icon"])
        self._icon.text_color = list(config["color"])
        self._icon.opacity = 0 if spinner_active else 1

        display_text = str(self.text or "").strip()
        if not display_text:
            display_text = self._state_text(state)
        self._label.text = display_text
        self._label.text_color = list(config["color"] if state != "idle" else TEXT_SECONDARY)
        self._label.opacity = 1 if self.show_text else 0
        self._label.disabled = not bool(self.show_text)

        target_opacity = 1.0 if self.active or state in {"loading", "complete", "error"} else 0.75
        self.opacity = target_opacity

    def set_pull(self, text: str | None = None):
        self.state = "pull"
        self.active = False
        self.text = str(text or self.pull_text or "Pull to refresh")
        self._pulse()

    def set_release(self, text: str | None = None):
        self.state = "release"
        self.active = False
        self.text = str(text or self.release_text or "Release to refresh")
        self._pulse()

    def set_loading(self, text: str | None = None):
        self.state = "loading"
        self.active = True
        self.text = str(text or self.loading_text or "Refreshing...")
        self._pulse()

    def set_complete(self, text: str | None = None, *, auto_reset: bool = True):
        self.state = "complete"
        self.active = False
        self.text = str(text or self.complete_text or "Refresh complete")
        self._pulse()
        if auto_reset:
            Clock.schedule_once(lambda _dt: self.reset(), float(self.auto_reset_delay or 1.2))

    def set_error(self, text: str | None = None, *, auto_reset: bool = True):
        self.state = "error"
        self.active = False
        self.text = str(text or self.error_text or "Refresh failed")
        self._pulse()
        if auto_reset:
            Clock.schedule_once(lambda _dt: self.reset(), float(self.auto_reset_delay or 1.2))

    def reset(self):
        self.state = "idle"
        self.active = False
        self.text = str(self.pull_text or "Pull to refresh")
        self._pulse()

    def trigger_refresh(self, *args, message: str | None = None):
        self.set_loading(message)
        callback = self.refresh_callback
        if not callable(callback):
            return
        try:
            callback(self, *args)
        except TypeError:
            callback(*args)

    def finish_refresh(self, text: str | None = None):
        self.set_complete(text=text, auto_reset=True)

    def fail_refresh(self, text: str | None = None):
        self.set_error(text=text, auto_reset=True)

    def _pulse(self):
        Animation.cancel_all(self, "opacity")
        self.opacity = 0.86
        Animation(opacity=1.0, duration=float(self.refresh_duration or 0.18), t="out_quad").start(self)


try:
    from kivy.factory import Factory

    Factory.register("RefreshIndicator", cls=RefreshIndicator)
except Exception:
    pass
