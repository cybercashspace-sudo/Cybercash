from __future__ import annotations

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle


class AnimationManager:
    """Shared animation helpers used across screens and components."""

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
    def scale_pop(widget, *, shrink: float = 0.8, duration: float = 0.35, delay: float = 0.0):
        if widget is None:
            return

        def _start(_dt):
            if hasattr(widget, "scale_value"):
                widget.scale_value = float(shrink)
                Animation(
                    scale_value=1.0,
                    duration=duration,
                    transition="out_back",
                ).start(widget)
                return

            if hasattr(widget, "scale"):
                try:
                    widget.scale = float(shrink)
                    Animation(
                        scale=1.0,
                        duration=duration,
                        transition="out_back",
                    ).start(widget)
                    return
                except Exception:
                    pass

            base_opacity = float(getattr(widget, "opacity", 1.0))
            Animation(
                opacity=max(0.85, base_opacity * float(shrink)),
                duration=duration * 0.35,
                transition="out_quad",
            ).start(widget)
            Animation(
                opacity=base_opacity,
                duration=duration,
                transition="out_quad",
            ).start(widget)

        Clock.schedule_once(_start, delay)

    @staticmethod
    def pulse(widget, *, shrink: float = 0.97, duration: float = 0.1):
        AnimationManager.scale_pop(widget, shrink=shrink, duration=duration)


class HomeAnimations:
    """Entrance and emphasis animations for the dashboard."""

    @staticmethod
    def fade_slide(widget, delay: float = 0.0, y_offset: float = 40, duration: float = 0.45):
        AnimationManager.slide_up(widget, distance=y_offset, duration=duration, delay=delay)

    @staticmethod
    def pop_card(widget, delay: float = 0.0):
        if widget is None:
            return

        origin_y = getattr(widget, "_cybercash_origin_y", widget.y)
        widget._cybercash_origin_y = origin_y

        def _start(_dt):
            widget.opacity = 0
            widget.y = origin_y - 24
            if hasattr(widget, "scale_value"):
                widget.scale_value = 0.85
                Animation(scale_value=1.0, duration=0.55, transition="out_back").start(widget)
            elif hasattr(widget, "scale"):
                try:
                    widget.scale = 0.85
                    Animation(scale=1.0, duration=0.55, transition="out_back").start(widget)
                except Exception:
                    pass
            Animation(y=origin_y, opacity=1, duration=0.55, transition="out_back").start(widget)

        Clock.schedule_once(_start, delay)

    @staticmethod
    def fade(widget, delay: float = 0.0, duration: float = 0.35):
        AnimationManager.fade_in(widget, duration=duration, delay=delay)


class ShimmerEffect:
    """Lightweight moving highlight for the wallet card."""

    def __init__(self, widget, *, speed: float = 5.0, width: float = 84.0, opacity: float = 0.14):
        self.widget = widget
        self.speed = float(speed)
        self.width = float(width)
        self.opacity = float(opacity)
        self.position = -self.width * 3
        self._event = None
        self._color = None
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
        if self._stripe is not None:
            try:
                self._stripe.opacity = 0
            except Exception:
                pass
        self._stripe = None
        self._color = None

    def _sync_canvas(self):
        if self.widget is None:
            return
        if self._stripe is None or self._color is None:
            with self.widget.canvas.after:
                self._color = Color(1, 0.78, 0.15, self.opacity)
                self._stripe = Rectangle(
                    pos=(self.widget.x + self.position, self.widget.y),
                    size=(self.width, self.widget.height),
                )
            return

        self._color.rgba = (1, 0.78, 0.15, self.opacity)
        self._stripe.pos = (self.widget.x + self.position, self.widget.y)
        self._stripe.size = (self.width, self.widget.height)

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


class DashboardAnimationSequence:
    """Coordinates the premium home dashboard entrance animation."""

    @staticmethod
    def _slide_up_delayed(
        widget: Widget | None,
        *,
        distance: float,
        duration: float,
        delay: float,
    ) -> None:
        if widget is None:
            return

        HomeAnimations.fade_slide(widget, delay=delay, y_offset=distance, duration=duration)

    @staticmethod
    def play(
        *,
        wallet_card: Widget | None,
        balance_panel: Widget | None,
        action_buttons: Widget | None,
        transactions: Widget | None,
        promotions: Widget | None = None,
        bottom_navigation: Widget | None = None,
        shimmer_card: Widget | None = None,
    ) -> None:
        for widget in (balance_panel, action_buttons, promotions, transactions, bottom_navigation):
            if widget is not None:
                widget.opacity = 0

        if shimmer_card is not None and hasattr(shimmer_card, "start_shimmer"):
            Clock.schedule_once(lambda _dt: shimmer_card.start_shimmer(), 0.15)

        HomeAnimations.pop_card(wallet_card, delay=0)
        DashboardAnimationSequence._slide_up_delayed(
            balance_panel,
            distance=35,
            duration=0.6,
            delay=0.15,
        )
        DashboardAnimationSequence._slide_up_delayed(
            action_buttons,
            distance=45,
            duration=0.7,
            delay=0.3,
        )
        DashboardAnimationSequence._slide_up_delayed(
            promotions,
            distance=52,
            duration=0.75,
            delay=0.38,
        )
        DashboardAnimationSequence._slide_up_delayed(
            transactions,
            distance=60,
            duration=0.8,
            delay=0.45,
        )
        HomeAnimations.fade(bottom_navigation, delay=0.65, duration=0.5)
