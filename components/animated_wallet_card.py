from __future__ import annotations

from components.wallet_card import WalletCard


class AnimatedWalletCard(WalletCard):
    """Compatibility alias for the reusable premium wallet card."""


try:
    from kivy.factory import Factory

    Factory.register("AnimatedWalletCard", cls=AnimatedWalletCard)
except Exception:
    pass
