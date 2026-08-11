from __future__ import annotations

from features.transfer.transfer_service import TransferService
from features.transfer.validators import validate_amount, validate_pin, validate_recipient


class TransferController:
    def __init__(self, service: TransferService | None = None):
        self.service = service or TransferService()

    def lookup_recipient(self, recipient: str) -> dict:
        recipient_value = validate_recipient(recipient)
        return self.service.validate_recipient(recipient_value)

    def transfer(self, recipient, amount, pin, description: str = ""):
        recipient_value = validate_recipient(recipient)
        amount_value = validate_amount(amount)
        pin_value = validate_pin(pin)
        payload = {
            "recipient": recipient_value,
            "amount": amount_value,
            "pin": pin_value,
            "description": str(description or "").strip(),
        }
        return self.service.send_money(payload)
