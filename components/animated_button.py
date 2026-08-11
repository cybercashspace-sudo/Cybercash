from __future__ import annotations

from kivy.animation import Animation
from kivy.properties import NumericProperty
from kivymd.uix.button import MDRaisedButton


class AnimatedButton(MDRaisedButton):
    """Button with a subtle press animation."""

    press_scale = NumericProperty(0.97)

    def animate_press(self):
        Animation(opacity=0.92, duration=0.06).start(self)
        Animation(opacity=1.0, duration=0.12).start(self)


try:
    from kivy.factory import Factory

    Factory.register("AnimatedButton", cls=AnimatedButton)
except Exception:
    pass

