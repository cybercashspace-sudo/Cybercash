from __future__ import annotations

from components.transaction_card import TransactionCard


try:
    from kivy.factory import Factory

    Factory.register("TransactionCard", cls=TransactionCard)
except Exception:
    pass
