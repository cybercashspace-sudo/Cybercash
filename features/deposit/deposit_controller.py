from __future__ import annotations

from features.deposit.deposit_service import DepositService
from features.deposit.validators import validate_amount, validate_method


class DepositController:
    def __init__(self, service: DepositService | None = None):
        self.service = service or DepositService()

    def start_deposit(self, amount, method):
        amount_value = validate_amount(amount)
        method_value = validate_method(method)
        return self.service.create_deposit(amount_value, method_value)

    def verify_payment(self, reference: str):
        return self.service.verify_payment(reference)
