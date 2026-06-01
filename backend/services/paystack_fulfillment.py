from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.core.config import settings
from backend.models import Agent, JournalEntry, Transaction, User, Wallet
from backend.services.agent_startup_loan import grant_startup_loan_credit
from backend.services.ledger_service import LedgerService
from backend.services.settings_service import get_or_create_platform_settings


AGENT_REGISTRATION_TX_TYPE: Final[str] = "agent_registration_fee"
GHS_QUANTIZER: Final[Decimal] = Decimal("0.01")
PAYSTACK_PENDING_STATUSES: Final[set[str]] = {
    "pending",
    "ongoing",
    "processing",
    "queued",
    "abandoned",
}


def to_ghs_decimal(value: object) -> Decimal:
    try:
        return Decimal(str(value)).quantize(GHS_QUANTIZER, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Invalid GHS amount.") from exc


def ghs_to_paystack_subunit(value: object) -> int:
    return int((to_ghs_decimal(value) * Decimal("100")).to_integral_value(rounding=ROUND_HALF_UP))


def paystack_kobo_to_ghs(value: object) -> Decimal:
    try:
        return (Decimal(str(value)) / Decimal("100")).quantize(GHS_QUANTIZER, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Invalid Paystack amount.") from exc


def paystack_amount_matches(provider_amount_kobo: object, expected_amount_ghs: object) -> bool:
    return paystack_kobo_to_ghs(provider_amount_kobo) == to_ghs_decimal(expected_amount_ghs)


def paystack_currency_matches(provider_currency: object, expected_currency: object = "GHS") -> bool:
    provider = str(provider_currency or "").strip().upper()
    expected = str(expected_currency or "GHS").strip().upper()
    return not provider or provider == expected


async def _get_or_create_wallet(db: AsyncSession, user_id: int, currency: str = "GHS") -> Wallet:
    result = await db.execute(select(Wallet).filter(Wallet.user_id == user_id).with_for_update())
    wallet = result.scalars().first()
    if wallet:
        return wallet

    wallet = Wallet(user_id=user_id, currency=currency or "GHS", balance=0.0)
    db.add(wallet)
    await db.flush()
    return wallet


async def _get_or_create_agent(db: AsyncSession, user_id: int) -> Agent:
    result = await db.execute(select(Agent).filter(Agent.user_id == user_id).with_for_update())
    agent = result.scalars().first()
    if agent:
        return agent

    platform_settings = await get_or_create_platform_settings(db)
    agent = Agent(
        user_id=user_id,
        status="pending",
        commission_rate=float(platform_settings.commission_rate or settings.AGENT_COMMISSION_RATE),
        float_balance=0.0,
    )
    db.add(agent)
    await db.flush()
    return agent


async def _ensure_agent_registration_fee_journal(db: AsyncSession, transaction: Transaction) -> None:
    if not transaction.id:
        await db.flush()

    existing_result = await db.execute(
        select(JournalEntry).filter(JournalEntry.transaction_id == transaction.id)
    )
    if existing_result.scalars().first():
        return

    amount = float(to_ghs_decimal(transaction.amount))
    ledger_service = LedgerService(db)
    await ledger_service.create_journal_entry(
        description=f"Paystack agent registration fee for user {transaction.user_id}",
        ledger_entries_data=[
            {"account_name": "Cash (External Bank)", "debit": amount, "credit": 0.0},
            {"account_name": "Revenue - Agent Fees", "debit": 0.0, "credit": amount},
        ],
        transaction=transaction,
        auto_commit=False,
    )


async def complete_paid_agent_registration(db: AsyncSession, transaction: Transaction) -> Agent:
    """
    Idempotently activate an agent after a confirmed Paystack registration fee.
    This is shared by polling and webhook flows so the phone does not have to
    be online at the exact callback moment.
    """
    if transaction.type != AGENT_REGISTRATION_TX_TYPE:
        raise ValueError("Transaction is not an agent registration fee.")

    user_id = int(transaction.user_id)
    currency = str(transaction.currency or "GHS").strip().upper() or "GHS"

    wallet = None
    if transaction.wallet_id:
        result = await db.execute(select(Wallet).filter(Wallet.id == transaction.wallet_id).with_for_update())
        wallet = result.scalars().first()
    if not wallet:
        wallet = await _get_or_create_wallet(db, user_id, currency=currency)
        transaction.wallet_id = wallet.id

    agent = await _get_or_create_agent(db, user_id)
    agent.status = "active"
    db.add(agent)

    result = await db.execute(select(User).filter(User.id == user_id).with_for_update())
    user = result.scalars().first()
    if user:
        user.is_agent = True
        db.add(user)

    transaction.status = "completed"
    db.add(transaction)
    await db.flush()

    await _ensure_agent_registration_fee_journal(db, transaction)

    await grant_startup_loan_credit(
        db,
        user_id=user_id,
        wallet_id=wallet.id,
        agent=agent,
        amount=settings.AGENT_STARTUP_LOAN_AMOUNT,
        currency=currency,
    )

    await db.commit()
    result = await db.execute(
        select(Agent).options(selectinload(Agent.user)).filter(Agent.id == agent.id)
    )
    return result.scalars().first()
