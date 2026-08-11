from __future__ import annotations

from kivy.animation import Animation
from kivy.clock import Clock


class AnimationManager:
    """Shared animation helpers used across screens."""

    @staticmethod
    def fade_in(widget, duration: float = 0.5, delay: float = 0.0):
        if widget is None:
            return

        def _start(_dt):
            widget.opacity = 0
            Animation(opacity=1, duration=duration, transition="out_quad").start(widget)

        Clock.schedule_once(_start, delay)

    @staticmethod
    def fade_out(widget, duration: float = 0.35, delay: float = 0.0):
        if widget is None:
            return

        def _start(_dt):
            Animation(opacity=0, duration=duration, transition="out_quad").start(widget)

        Clock.schedule_once(_start, delay)

    @staticmethod
    def slide_up(widget, distance: float = 40, duration: float = 0.45, delay: float = 0.0):
        if widget is None:
            return

        origin_y = getattr(widget, "_cybercash_origin_y", widget.y)
        widget._cybercash_origin_y = origin_y

        def _start(_dt):
            widget.opacity = 0
            widget.y = origin_y - distance
            Animation(y=origin_y, opacity=1, duration=duration, transition="out_cubic").start(widget)

        Clock.schedule_once(_start, delay)

    @staticmethod
    def pulse(widget, *, shrink: float = 0.97, duration: float = 0.1):
        if widget is None:
            return
        if hasattr(widget, "scale_value"):
            Animation(scale_value=shrink, duration=duration, transition="out_quad").start(widget)
            Animation(scale_value=1.0, duration=duration * 1.5, transition="out_quad").start(widget)
            return
        Animation(opacity=max(0.85, float(getattr(widget, "opacity", 1.0))), duration=duration).start(widget)
        Animation(opacity=1.0, duration=duration * 1.5).start(widget)

