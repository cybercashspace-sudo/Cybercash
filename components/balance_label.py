from __future__ import annotations

from kivy.properties import StringProperty

from .balance_counter import BalanceCounter


class BalanceLabel(BalanceCounter):
    """Currency label alias with the correct Ghana cedi symbol."""

    currency_symbol = StringProperty("GH\u20B5")


try:
    from kivy.factory import Factory

    Factory.register("BalanceLabel", cls=BalanceLabel)
except Exception:
    pass
