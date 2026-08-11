from __future__ import annotations

from features.withdrawal.validators import (
    detect_network,
    validate_amount,
    validate_network,
    validate_phone,
    validate_pin,
)
from features.withdrawal.withdrawal_service import WithdrawalService


class WithdrawalController:
    def __init__(self, service: WithdrawalService | None = None):
        self.service = service or WithdrawalService()

    def withdraw(self, amount, network, phone, pin):
        amount_value = validate_amount(amount)
        phone_value = validate_phone(phone)
        network_value = str(network or "").strip().lower() or detect_network(phone_value)
        if network_value == "auto":
            network_value = detect_network(phone_value)
        network_value = validate_network(network_value)
        pin_value = validate_pin(pin)
        payload = {
            "amount": amount_value,
            "network": network_value,
            "phone": phone_value,
            "pin": pin_value,
        }
        return self.service.create_withdrawal(payload)

    @staticmethod
    def detect_network(phone: str) -> str:
        return detect_network(phone)

    def check_status(self, withdrawal_id: str):
        return self.service.check_status(withdrawal_id)
