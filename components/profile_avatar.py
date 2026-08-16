from __future__ import annotations

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import NumericProperty, StringProperty
from kivymd.uix.fitimage import FitImage

from theme import PILL_RADIUS


class ProfileAvatar(FitImage):
    """Reusable avatar image with a circular crop."""

    source = StringProperty("assets/profile.png")
    diameter = NumericProperty(72)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (None, None)
        self.radius = list(PILL_RADIUS)
        self.bind(diameter=self._sync_size)
        Clock.schedule_once(self._sync_size, 0)

    def _sync_size(self, *_args):
        size = dp(float(self.diameter or 72))
        self.size = (size, size)


try:
    from kivy.factory import Factory

    Factory.register("ProfileAvatar", cls=ProfileAvatar)
except Exception:
    pass
