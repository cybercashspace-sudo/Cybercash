from __future__ import annotations

from kivy.animation import Animation
from kivy.clock import Clock


class AuthAnimations:
    @staticmethod
    def enter(widget, delay: float = 0.0, duration: float = 0.35):
        def _animate(*_args):
            if widget is None:
                return
            widget.opacity = 0
            Animation(opacity=1, duration=duration, transition="out_quad").start(widget)

        Clock.schedule_once(_animate, delay)

    @staticmethod
    def slide(widget, delay: float = 0.0, distance: float = 24.0, duration: float = 0.45):
        def _animate(*_args):
            if widget is None:
                return
            original_y = widget.y
            widget.opacity = 0
            widget.y = original_y - distance
            Animation(
                y=original_y,
                opacity=1,
                duration=duration,
                transition="out_cubic",
            ).start(widget)

        Clock.schedule_once(_animate, delay)

    @staticmethod
    def pop(widget, delay: float = 0.0, duration: float = 0.35):
        def _animate(*_args):
            if widget is None:
                return
            if hasattr(widget, "scale"):
                widget.scale = 0.92
                Animation(scale=1.0, duration=duration, transition="out_back").start(widget)
            else:
                Animation(opacity=1, duration=duration, transition="out_quad").start(widget)

        Clock.schedule_once(_animate, delay)
