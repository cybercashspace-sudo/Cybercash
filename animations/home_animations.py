from __future__ import annotations

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle


class HomeAnimations:
    """Entrance and emphasis animations for the dashboard."""

    @staticmethod
    def fade_slide(widget, delay: float = 0.0, y_offset: float = 40, duration: float = 0.45):
        if widget is None:
            return

        origin_y = getattr(widget, "_cybercash_origin_y", widget.y)
        widget._cybercash_origin_y = origin_y

        def _start(_dt):
            widget.opacity = 0
            widget.y = origin_y - y_offset
            Animation(y=origin_y, opacity=1, duration=duration, transition="out_cubic").start(widget)

        Clock.schedule_once(_start, delay)

    @staticmethod
    def pop_card(widget, delay: float = 0.0):
        if widget is None:
            return

        origin_y = getattr(widget, "_cybercash_origin_y", widget.y)
        widget._cybercash_origin_y = origin_y

        def _start(_dt):
            widget.opacity = 0
            widget.y = origin_y - 24
            Animation(y=origin_y, opacity=1, duration=0.55, transition="out_back").start(widget)

        Clock.schedule_once(_start, delay)

    @staticmethod
    def fade(widget, delay: float = 0.0, duration: float = 0.35):
        if widget is None:
            return

        def _start(_dt):
            widget.opacity = 0
            Animation(opacity=1, duration=duration, transition="out_quad").start(widget)

        Clock.schedule_once(_start, delay)


class ShimmerEffect:
    """Lightweight moving highlight for the wallet card."""

    def __init__(self, widget, *, speed: float = 5.0, width: float = 84.0, opacity: float = 0.14):
        self.widget = widget
        self.speed = float(speed)
        self.width = float(width)
        self.opacity = float(opacity)
        self.position = -self.width * 3
        self._event = None
        self._stripe = None

    def start(self):
        if self.widget is None or self._event is not None:
            return
        self._sync_canvas()
        self._event = Clock.schedule_interval(self._step, 0.02)

    def stop(self):
        if self._event is not None:
            try:
                self._event.cancel()
            except Exception:
                pass
        self._event = None
        if self.widget is not None:
            try:
                self.widget.canvas.after.clear()
            except Exception:
                pass
        self._stripe = None

    def _sync_canvas(self):
        if self.widget is None:
            return
        try:
            self.widget.canvas.after.clear()
        except Exception:
            return
        with self.widget.canvas.after:
            Color(1, 0.78, 0.15, self.opacity)
            self._stripe = Rectangle(pos=(self.widget.x + self.position, self.widget.y), size=(self.width, self.widget.height))

    def _step(self, _dt):
        if self.widget is None:
            return False
        self.position += self.speed
        if self.position > self.widget.width + self.width:
            self.position = -self.width * 3
        if self._stripe is None:
            self._sync_canvas()
            return True
        self._stripe.pos = (self.widget.x + self.position, self.widget.y)
        self._stripe.size = (self.width, self.widget.height)
        return True

