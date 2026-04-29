from __future__ import annotations

from typing import Final


class TransactionType:
    FUNDING: Final[str] = "FUNDING"
    TRANSFER: Final[str] = "TRANSFER"
    AGENT_DEPOSIT: Final[str] = "AGENT_DEPOSIT"
    AGENT_WITHDRAWAL: Final[str] = "AGENT_WITHDRAWAL"
    AIRTIME: Final[str] = "AIRTIME"
    DATA: Final[str] = "DATA"
    ESCROW_CREATE: Final[str] = "ESCROW_CREATE"
    ESCROW_RELEASE: Final[str] = "ESCROW_RELEASE"
    CARD_SPEND: Final[str] = "CARD_SPEND"
    CARD_LOAD: Final[str] = "CARD_LOAD"
    CARD_WITHDRAW: Final[str] = "CARD_WITHDRAW"
    VIRTUAL_CARD_ISSUANCE_FEE: Final[str] = "VIRTUAL_CARD_ISSUANCE_FEE"
    BTC_DEPOSIT: Final[str] = "BTC_DEPOSIT"
    BTC_WITHDRAW: Final[str] = "BTC_WITHDRAW"
    LOAN_DISBURSE: Final[str] = "LOAN_DISBURSE"
    LOAN_REPAY: Final[str] = "LOAN_REPAY"
    INVESTMENT_CREATE: Final[str] = "INVESTMENT_CREATE"
    INVESTMENT_PAYOUT: Final[str] = "INVESTMENT_PAYOUT"
    MOBILE_MONEY: Final[str] = "MOBILE_MONEY"
    ESCROW_FEE: Final[str] = "ESCROW_FEE"


_ALIASES: Final[dict[str, str]] = {
    "DEPOSIT": TransactionType.FUNDING,
    "deposit": TransactionType.FUNDING,
    "FUNDING": TransactionType.FUNDING,
    "funding": TransactionType.FUNDING,
    "CASH_DEPOSIT": TransactionType.AGENT_DEPOSIT,
    "cash_deposit": TransactionType.AGENT_DEPOSIT,
    "CASH_WITHDRAWAL": TransactionType.AGENT_WITHDRAWAL,
    "cash_withdrawal": TransactionType.AGENT_WITHDRAWAL,
    "P2P_TRANSFER": TransactionType.TRANSFER,
    "transfer_send": TransactionType.TRANSFER,
    "transfer_receive": TransactionType.TRANSFER,
    "AIRTIME_PURCHASE": TransactionType.AIRTIME,
    "DATA_PURCHASE": TransactionType.DATA,
    "ESCROW_LOCK": TransactionType.ESCROW_CREATE,
    "VIRTUAL_CARD_LOAD": TransactionType.CARD_LOAD,
    "VIRTUAL_CARD_WITHDRAWAL": TransactionType.CARD_WITHDRAW,
    "VIRTUAL_CARD_ISSUANCE_FEE": TransactionType.VIRTUAL_CARD_ISSUANCE_FEE,
    "virtual_card_issuance_fee": TransactionType.VIRTUAL_CARD_ISSUANCE_FEE,
    "CARD_SPEND": TransactionType.CARD_SPEND,
    "CRYPTO_DEPOSIT": TransactionType.BTC_DEPOSIT,
    "CRYPTO_WITHDRAWAL": TransactionType.BTC_WITHDRAW,
    "LOAN_DISBURSEMENT": TransactionType.LOAN_DISBURSE,
    "LOAN_REPAYMENT": TransactionType.LOAN_REPAY,
    "INVESTMENT_DEPOSIT": TransactionType.INVESTMENT_CREATE,
    "INVESTMENT_WITHDRAWAL": TransactionType.INVESTMENT_PAYOUT,
    "momo_withdrawal": TransactionType.MOBILE_MONEY,
    "mobile_money_payout": TransactionType.MOBILE_MONEY,
}


def normalize_transaction_type(transaction_type: str) -> str:
    if not transaction_type:
        raise ValueError("Transaction type is required.")
    return _ALIASES.get(transaction_type, transaction_type.upper())
