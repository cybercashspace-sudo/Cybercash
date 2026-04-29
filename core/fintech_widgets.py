from __future__ import annotations

from functools import lru_cache

from kivy.graphics import Color, Line
from kivy.graphics.texture import Texture
from kivy.graphics.vertex_instructions import RoundedRectangle
from kivy.metrics import dp
from kivy.properties import ListProperty, NumericProperty, OptionProperty
from kivymd.uix.card import MDCard


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


@lru_cache(maxsize=256)
def _gradient_texture(
    start_rgba: tuple[float, float, float, float],
    end_rgba: tuple[float, float, float, float],
    direction: str,
    steps: int,
) -> Texture:
    steps = max(4, int(steps or 64))
    horizontal = direction == "horizontal"
    width, height = (steps, 1) if horizontal else (1, steps)

    texture = Texture.create(size=(width, height), colorfmt="rgba")
    buffer = bytearray()

    for i in range(steps):
        t = i / (steps - 1) if steps > 1 else 0.0
        r = start_rgba[0] + (end_rgba[0] - start_rgba[0]) * t
        g = start_rgba[1] + (end_rgba[1] - start_rgba[1]) * t
        b = start_rgba[2] + (end_rgba[2] - start_rgba[2]) * t
        a = start_rgba[3] + (end_rgba[3] - start_rgba[3]) * t
        buffer.extend(
            (
                int(_clamp01(r) * 255),
                int(_clamp01(g) * 255),
                int(_clamp01(b) * 255),
                int(_clamp01(a) * 255),
            )
        )

    if horizontal:
        # RGBA pixels across X.
        texture.blit_buffer(bytes(buffer), colorfmt="rgba", bufferfmt="ubyte")
    else:
        # Duplicate column for each row (1px wide).
        texture.blit_buffer(bytes(buffer), colorfmt="rgba", bufferfmt="ubyte")

    texture.mag_filter = "linear"
    texture.min_filter = "linear"
    return texture


class GradientMDCard(MDCard):
    """
    MDCard with a lightweight gradient fill (fintech-style).

    Use `gradient_start` / `gradient_end` and `gradient_direction`.
    """

    gradient_start = ListProperty([0.831, 0.686, 0.216, 1])  # #D4AF37
    gradient_end = ListProperty([0.965, 0.886, 0.478, 1])  # #F6E27A
    gradient_direction = OptionProperty("horizontal", options=("horizontal", "vertical"))
    gradient_steps = NumericProperty(64)
    border_color = ListProperty([1, 1, 1, 0.08])
    border_width = NumericProperty(1.0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Let the gradient show through.
        try:
            self.md_bg_color = [0, 0, 0, 0]
        except Exception:
            pass

        with self.canvas.before:
            self._fill_color = Color(1, 1, 1, 1)
            self._fill_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=self._resolved_radius())
            self._stroke_color = Color(*self.border_color)
            self._stroke_line = Line(width=float(self.border_width or 1.0))

        self.bind(pos=self._redraw, size=self._redraw, radius=self._redraw)
        self.bind(
            gradient_start=self._sync_texture,
            gradient_end=self._sync_texture,
            gradient_direction=self._sync_texture,
            gradient_steps=self._sync_texture,
            border_color=self._sync_border,
            border_width=self._sync_border,
        )

        self._sync_texture()
        self._sync_border()
        self._redraw()

    def _resolved_radius(self):
        radius = getattr(self, "radius", None)
        if isinstance(radius, (list, tuple)) and radius:
            value = radius[0]
            if isinstance(value, (list, tuple)) and value:
                value = value[0]
            try:
                value = float(value)
            except Exception:
                value = float(dp(16))
            return [value, value, value, value]
        return [float(dp(16))] * 4

    def _resolved_line_radius(self) -> float:
        resolved = self._resolved_radius()
        try:
            return float(resolved[0])
        except Exception:
            return float(dp(16))

    def _sync_texture(self, *_args) -> None:
        start = tuple(float(x) for x in (self.gradient_start or [0, 0, 0, 1]))
        end = tuple(float(x) for x in (self.gradient_end or [1, 1, 1, 1]))
        direction = str(self.gradient_direction or "horizontal")
        steps = int(self.gradient_steps or 64)
        self._fill_rect.texture = _gradient_texture(start, end, direction, steps)

    def _sync_border(self, *_args) -> None:
        try:
            self._stroke_color.rgba = list(self.border_color or [1, 1, 1, 0.08])
        except Exception:
            pass
        try:
            self._stroke_line.width = float(self.border_width or 1.0)
        except Exception:
            pass
        self._redraw()

    def _redraw(self, *_args) -> None:
        self._fill_rect.pos = self.pos
        self._fill_rect.size = self.size
        self._fill_rect.radius = self._resolved_radius()

        radius = self._resolved_line_radius()
        self._stroke_line.rounded_rectangle = (self.x, self.y, self.width, self.height, radius)


try:
    from kivy.factory import Factory

    Factory.register("GradientMDCard", cls=GradientMDCard)
except Exception:
    pass

