from __future__ import annotations

from components.animated_card import AnimatedCard


class TransactionCard(AnimatedCard):
    """Reusable card used for recent transactions."""


try:
    from kivy.factory import Factory

    Factory.register("TransactionCard", cls=TransactionCard)
except Exception:
    pass

