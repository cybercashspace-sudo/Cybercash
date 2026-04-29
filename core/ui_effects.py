from __future__ import annotations

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.graphics import Color, Line, PopMatrix, PushMatrix, Rotate
from kivy.metrics import dp
from kivy.properties import BooleanProperty, ListProperty, NumericProperty
from kivy.uix.widget import Widget


def shake(widget, *, intensity: float = 10.0, duration: float = 0.05) -> Animation:
    """
    Small horizontal shake (fintech-style error cue).
    Works best on widgets with a stable `x` position.
    """
    base_x = float(getattr(widget, "x", 0.0) or 0.0)
    anim = (
        Animation(x=base_x - intensity, duration=duration)
        + Animation(x=base_x + intensity, duration=duration)
        + Animation(x=base_x - intensity * 0.6, duration=duration)
        + Animation(x=base_x + intensity * 0.6, duration=duration)
        + Animation(x=base_x, duration=duration)
    )
    anim.start(widget)
    return anim


class FintechSpinner(Widget):
    """
    Lightweight circular spinner without relying on KivyMD internals.
    Toggle with `active=True/False`.
    """

    active = BooleanProperty(False)
    speed = NumericProperty(240.0)  # degrees per second
    color = ListProperty([0.831, 0.686, 0.216, 1])  # Gold
    line_width = NumericProperty(0.0)  # 0 => auto

    _tick_event = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._angle = 0.0

        with self.canvas:
            PushMatrix()
            self._rot = Rotate(angle=0.0, origin=self.center)
            self._color = Color(*self.color)
            self._arc = Line(circle=(0, 0, 0, 20, 320), width=self._resolved_width(), cap="round")
            PopMatrix()

        self.bind(pos=self._update_canvas, size=self._update_canvas)
        self.bind(color=self._update_color)
        self.bind(line_width=self._update_canvas)
        self.bind(active=self._toggle)

        self._update_canvas()
        if self.active:
            self._start()

    def _resolved_width(self) -> float:
        configured = float(self.line_width or 0.0)
        return configured if configured > 0 else dp(3)

    def _update_color(self, *_args) -> None:
        try:
            self._color.rgba = list(self.color)
        except Exception:
            pass

    def _update_canvas(self, *_args) -> None:
        radius = max(0.0, min(float(self.width), float(self.height)) / 2.0 - dp(2))
        self._rot.origin = self.center
        self._arc.circle = (self.center_x, self.center_y, radius, 20, 320)
        self._arc.width = self._resolved_width()

    def _toggle(self, *_args) -> None:
        if self.active:
            self._start()
        else:
            self._stop()

    def _start(self) -> None:
        if self._tick_event is not None:
            return
        self._tick_event = Clock.schedule_interval(self._tick, 1 / 60)

    def _stop(self) -> None:
        if self._tick_event is not None:
            try:
                self._tick_event.cancel()
            except Exception:
                pass
        self._tick_event = None

    def _tick(self, dt: float) -> None:
        self._angle = (self._angle + float(self.speed or 0.0) * float(dt or 0.0)) % 360.0
        self._rot.angle = self._angle


try:
    from kivy.factory import Factory

    Factory.register("FintechSpinner", cls=FintechSpinner)
except Exception:
    # Factory registration is optional; screens can still instantiate directly.
    pass
