"""Reusable dashboard animation helpers for CYBER CASH."""

from __future__ import annotations

from kivy.clock import Clock
from kivy.uix.widget import Widget

from animations.home_animations import HomeAnimations


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
