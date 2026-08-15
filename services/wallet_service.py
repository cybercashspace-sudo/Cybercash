from __future__ import annotations

from features.home.home_service import HomeService as _HomeService
from models.transaction import Transaction
from models.user import User
from models.wallet import Wallet


class WalletService(_HomeService):
    """App-facing wallet and dashboard facade."""

    def get_user_model(self) -> User:
        return User.from_payload(self.get_profile())

    def get_wallet_model(self) -> Wallet:
        return Wallet.from_payload(self.get_wallet())

    def get_transaction_models(self, limit: int = 10) -> list[Transaction]:
        return [Transaction.from_payload(item) for item in self.get_transactions(limit=limit)]

    def get_dashboard_models(self) -> dict:
        data = self.get_dashboard()
        profile = data.get("profile") if isinstance(data.get("profile"), dict) else {}
        wallet = data.get("wallet") if isinstance(data.get("wallet"), dict) else {}
        transactions = data.get("transactions") if isinstance(data.get("transactions"), list) else []
        notifications = data.get("notifications") if isinstance(data.get("notifications"), list) else []
        return {
            "profile": User.from_payload(profile),
            "wallet": Wallet.from_payload(wallet),
            "transactions": [Transaction.from_payload(item) for item in transactions if isinstance(item, dict)],
            "notifications": [item for item in notifications if isinstance(item, dict)],
            "source": str(data.get("source") or "network"),
        }


__all__ = ["WalletService"]
