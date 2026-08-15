from __future__ import annotations

from models.wallet import Wallet
from services.api import api


class WalletService:
    def get_wallet(self):
        last_error = None
        for path in ("/wallet/me", "/api/wallet/me"):
            try:
                response = api.get(path)
                response.raise_for_status()
                payload = response.json()
                if isinstance(payload, dict):
                    return payload
            except Exception as exc:
                last_error = exc
                continue
        if last_error is not None:
            raise last_error
        return {}

    def refresh_balance(self):
        wallet = self.get_wallet()
        return wallet["balance"]

    def get_wallet_model(self) -> Wallet:
        return Wallet.from_payload(self.get_wallet())
