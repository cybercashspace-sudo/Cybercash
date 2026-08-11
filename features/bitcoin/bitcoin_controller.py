from datetime import datetime
from typing import Any, Dict, List

from features.bitcoin.bitcoin_service import BitcoinService
from features.bitcoin.models import BitcoinTransaction, BitcoinWallet
from features.bitcoin.price_service import PriceService
from features.bitcoin.validators import validate_btc_address, validate_btc_amount


def _to_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


class BitcoinController:
    def __init__(self):
        self.service = BitcoinService()
        self.price_service = PriceService()

    def load_dashboard(self, page: int = 1, limit: int = 10) -> Dict[str, Any]:
        wallet_raw = self.service.get_wallet() or {}
        price = self.price_service.get_btc_price()
        transactions = self.service.get_transactions(page=page, limit=limit)

        wallet = BitcoinWallet.from_dict(wallet_raw)
        return {
            "wallet": wallet,
            "price": float(price or 0.0),
            "price_text": f"${float(price or 0.0):,.2f}",
            "wallet_balance_text": f"₿ {wallet.balance:,.6f}",
            "wallet_usd_text": f"≈ GH₵ {wallet.usd_value:,.2f}",
            "wallet_address": wallet.address or "Not available",
            "wallet_status": wallet.status.replace("_", " ").title(),
            "transactions": self.normalize_transactions(transactions),
        }

    def refresh_price(self) -> Dict[str, Any]:
        price = self.price_service.get_btc_price()
        return {
            "price": float(price or 0.0),
            "price_text": f"${float(price or 0.0):,.2f}",
        }

    def normalize_transactions(self, transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [self._normalize_transaction(item) for item in transactions or []]

    def _normalize_transaction(self, item: Dict[str, Any]) -> Dict[str, Any]:
        tx = BitcoinTransaction.from_dict(item or {})
        return {
            "transaction_id": tx.transaction_id,
            "title": tx.title,
            "amount_text": tx.amount_text,
            "status": tx.status,
            "status_text": tx.status_text,
            "created_at": tx.created_at,
            "date_text": tx.date_text,
            "description": tx.description,
            "reference": tx.reference,
            "icon": _to_text(item.get("icon") or "bitcoin"),
        }

    def create_deposit_address(self):
        return self.service.create_deposit_address()

    def buy_btc(self, amount, pin=None, note=""):
        validated_amount = validate_btc_amount(amount)
        payload = {
            "amount": validated_amount,
            "pin": pin,
            "note": note,
        }
        return self.service.buy(payload)

    def sell_btc(self, amount, pin=None, note=""):
        validated_amount = validate_btc_amount(amount)
        payload = {
            "amount": validated_amount,
            "pin": pin,
            "note": note,
        }
        return self.service.sell(payload)

    def withdraw_btc(self, amount, address, pin=None, note=""):
        validated_amount = validate_btc_amount(amount)
        validated_address = validate_btc_address(address)
        payload = {
            "amount": validated_amount,
            "address": validated_address,
            "pin": pin,
            "note": note,
        }
        return self.service.withdraw(payload)

