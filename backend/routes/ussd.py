from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse
import requests
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend import models
from backend.core.config import settings
from backend.core.transaction_types import TransactionType
from backend.database import get_db
from backend.schemas.loan_application import LoanApplicationCreate
from backend.services import loan_service
from backend.services.momo import MomoService
from backend.services.transaction_engine import TransactionEngine, get_transaction_engine
from utils.network import detect_network, normalize_ghana_number
from utils.security import verify_pin

router = APIRouter()
logger = logging.getLogger(__name__)
momo_service = MomoService()

USSD_SHORTCODE = str(getattr(settings, "USSD_SHORTCODE", "*360#") or "*360#").strip() or "*360#"
P2P_DAILY_FREE_LIMIT_GHS = 100.0
P2P_TRANSFER_FEE_RATE = 0.005
INVESTMENT_ALLOWED_DURATIONS_DAYS = (7, 14, 30, 60, 90, 180, 365)
INVESTMENT_PROFIT_FEE_RATE = 0.10
WITHDRAW_FEE_RATE = float(getattr(settings, "TRANSACTION_FEE_PERCENTAGE", 0.01) or 0.01)
ESCROW_CREATE_FEE_GHS = float(getattr(settings, "ESCROW_CREATE_FEE_GHS", 5.0) or 5.0)
ESCROW_RELEASE_FEE_GHS = float(getattr(settings, "ESCROW_RELEASE_FEE_GHS", 5.0) or 5.0)
INVESTMENT_MIN_AMOUNT_GHS = float(getattr(settings, "INVESTMENT_MIN_AMOUNT_GHS", 10.0) or 10.0)
INVESTMENT_RISK_FREE_ANNUAL_RATE = float(
    getattr(settings, "INVESTMENT_RISK_FREE_ANNUAL_RATE", 12.0) or 12.0
)
BTC_USD_TO_GHS_RATE = float(getattr(settings, "BTC_USD_TO_GHS_RATE", 12.0) or 12.0)
BTC_MARKET_URL = str(
    getattr(settings, "BTC_MARKET_URL", "https://api.binance.com/api/v3/ticker/24hr?symbol=BTCUSDT")
    or "https://api.binance.com/api/v3/ticker/24hr?symbol=BTCUSDT"
).strip()
BTC_MARKET_TIMEOUT_SECONDS = float(getattr(settings, "BTC_MARKET_TIMEOUT_SECONDS", 8.0) or 8.0)


def _normalize_shortcode(value: str | None) -> str:
    return "".join(ch for ch in str(value or "") if ch not in {" ", "\t", "\n", "\r"}).strip().lower()


def _money(value: float | int | None) -> str:
    return f"GHS {float(value or 0.0):,.2f}"


def _btc_amount(value: float | int | None) -> str:
    return f"{float(value or 0.0):,.8f} BTC"


def _ghs_amount(value: float | int | None) -> str:
    return f"GHS {float(value or 0.0):,.2f}"


def _con(*lines: str) -> str:
    body = "\n".join(line for line in lines if line not in {None, ""})
    return f"CON {body}" if body else "CON"


def _end(*lines: str) -> str:
    body = "\n".join(line for line in lines if line not in {None, ""})
    return f"END {body}" if body else "END"


def _parse_metadata(raw_metadata: str | None) -> dict:
    if not raw_metadata:
        return {}
    try:
        parsed = json.loads(raw_metadata)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _parse_amount(raw_value: str | None) -> float:
    text = str(raw_value or "").replace(",", "").strip()
    if not text:
        raise ValueError("Enter an amount.")
    try:
        amount = round(float(text), 2)
    except ValueError as exc:
        raise ValueError("Enter a valid amount.") from exc
    if amount <= 0:
        raise ValueError("Amount must be greater than zero.")
    return amount


def _parse_days(raw_value: str | None) -> int:
    text = str(raw_value or "").strip()
    if not text:
        raise ValueError("Enter a valid number of days.")
    try:
        days = int(text)
    except ValueError as exc:
        raise ValueError("Enter a valid number of days.") from exc
    if days <= 0:
        raise ValueError("Days must be greater than zero.")
    return days


def _parse_phone(raw_value: str | None) -> str:
    phone_number = normalize_ghana_number(raw_value or "")
    if not phone_number or len(phone_number) != 10 or not phone_number.isdigit():
        raise ValueError("Enter a valid Ghana mobile number.")
    return phone_number


def _verify_access_pin(user: models.User, agent: models.Agent | None, pin: str | None) -> bool:
    raw_pin = str(pin or "").strip()
    if not raw_pin:
        return False

    if verify_pin(raw_pin, getattr(user, "pin_hash", None)):
        return True

    if agent and getattr(agent, "pin_hash", None):
        try:
            return bool(agent.verify_pin(raw_pin))
        except Exception:
            return False

    return False


def _security_context(
    user: models.User,
    session_id: str,
    phone_number: str,
    *,
    daily_limit: float | None = None,
) -> dict:
    limit = float(daily_limit if daily_limit is not None else (user.daily_limit or 0.0) or 0.0)
    if limit <= 0:
        limit = 10_000.0

    return {
        "pin_verified": True,
        "biometric_verified": True,
        "device_fingerprint": f"ussd:{user.id}:{session_id or phone_number}",
        "ip_address": "ussd-gateway",
        "channel": "USSD",
        "daily_limit": limit,
        "biometric_threshold": 1_000_000.0,
    }


async def _resolve_user_context(
    db: AsyncSession,
    raw_phone_number: str,
) -> tuple[models.User | None, models.Wallet | None, models.Agent | None]:
    phone_number = _parse_phone(raw_phone_number)

    result = await db.execute(
        select(models.User).filter(
            or_(
                models.User.momo_number == phone_number,
                models.User.phone_number == phone_number,
            )
        )
    )
    user = result.scalars().first()
    if not user:
        return None, None, None

    wallet_result = await db.execute(select(models.Wallet).filter(models.Wallet.user_id == user.id))
    wallet = wallet_result.scalars().first()

    agent_result = await db.execute(select(models.Agent).filter(models.Agent.user_id == user.id))
    agent = agent_result.scalars().first()
    if agent and str(agent.status or "").strip().lower() != "active":
        agent = None

    return user, wallet, agent


async def _ensure_wallet(db: AsyncSession, user_id: int) -> models.Wallet:
    result = await db.execute(select(models.Wallet).filter(models.Wallet.user_id == user_id))
    wallet = result.scalars().first()
    if wallet:
        return wallet

    wallet = models.Wallet(user_id=user_id, currency="GHS", balance=0.0)
    db.add(wallet)
    await db.flush()
    return wallet


async def _resolve_p2p_total_sent_today(db: AsyncSession, user_id: int) -> float:
    now = datetime.now(timezone.utc)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)

    result = await db.execute(
        select(models.Transaction).filter(
            models.Transaction.user_id == user_id,
            models.Transaction.type == TransactionType.TRANSFER,
            models.Transaction.status == "completed",
            models.Transaction.timestamp >= day_start,
            models.Transaction.timestamp < day_end,
        )
    )
    transactions = result.scalars().all()

    total_sent = 0.0
    for tx in transactions:
        metadata = _parse_metadata(tx.metadata_json)
        if str(metadata.get("direction", "")).strip().lower() != "send":
            continue
        if str(metadata.get("transfer_kind", "")).strip().lower() != "wallet_transfer":
            continue

        transferred_amount = metadata.get("transferred_amount")
        if transferred_amount is None:
            transferred_amount = max(
                0.0,
                abs(float(tx.amount or 0.0)) - float(metadata.get("transfer_fee", 0.0) or 0.0),
            )
        total_sent += float(transferred_amount or 0.0)

    return round(total_sent, 2)


def _back_requested(parts: list[str]) -> bool:
    return bool(parts) and str(parts[-1]).strip() == "0"


def _main_menu(agent: models.Agent | None) -> str:
    lines = [
        f"Cyber Cash ({USSD_SHORTCODE})",
        "1. Balance",
        "2. Send",
        "3. Withdraw",
        "4. Recharge",
        "5. Escrow",
        "6. Invest",
        "7. Loans",
        "8. BTC Balance",
    ]
    if agent:
        lines.append("9. Agent")
    return _con(*lines)


def _submenu(*lines: str) -> str:
    return _con(*lines, "0. Back to Menu")


async def _render_balance_menu(
    db: AsyncSession,
    user: models.User,
    agent: models.Agent | None,
    *,
    session_id: str,
    phone_number: str,
) -> str:
    snapshot = await loan_service.run_loan_maintenance_for_user(
        db=db,
        user_id=user.id,
        allow_auto_deduction=False,
    )
    wallet = snapshot.get("wallet")
    loan = snapshot.get("loan")

    lines = ["Balance"]
    lines.append(f"Main: {_money(getattr(wallet, 'balance', 0.0))}")

    loan_balance = float(getattr(loan, "remaining_balance", 0.0) or 0.0) if loan else 0.0
    if loan_balance > 0:
        lines.append(f"Loan: {_money(loan_balance)}")

    if agent:
        lines.append(f"Float: {_money(agent.float_balance)}")

    return _submenu(*lines)


async def _resolve_btc_wallet(db: AsyncSession, user_id: int) -> models.CryptoWallet | None:
    result = await db.execute(
        select(models.CryptoWallet).filter(
            models.CryptoWallet.user_id == user_id,
            models.CryptoWallet.coin_type == "BTC",
        )
    )
    return result.scalars().first()


def _fetch_btc_ghs_rate() -> float | None:
    try:
        response = requests.get(BTC_MARKET_URL, timeout=BTC_MARKET_TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json()
        last_price = float(payload.get("lastPrice") or payload.get("price") or 0.0)
        if last_price <= 0:
            return None
        return round(last_price * BTC_USD_TO_GHS_RATE, 2)
    except Exception as exc:
        logger.warning("BTC market data unavailable for USSD: %s", exc)
        return None


async def _render_btc_balance_menu(
    db: AsyncSession,
    user: models.User,
    *,
    session_id: str,
    phone_number: str,
) -> str:
    btc_wallet = await _resolve_btc_wallet(db, user.id)
    btc_balance = float(getattr(btc_wallet, "balance", 0.0) or 0.0)
    ghs_value = _fetch_btc_ghs_rate()

    lines = [
        "BTC Balance",
        f"Holdings: {_btc_amount(btc_balance)}",
    ]
    if ghs_value is None:
        lines.append("Value: unavailable")
    else:
        lines.append(f"Value: {_ghs_amount(btc_balance * ghs_value)}")

    return _submenu(*lines)


async def _render_agent_shortcut_menu(
    db: AsyncSession,
    user: models.User,
    agent: models.Agent,
    *,
    session_id: str,
    phone_number: str,
    parts: list[str],
) -> str:
    if not parts or parts[0] == "":
        return _submenu(
            "Agent",
            "1. Summary",
            "2. Loan Sweep",
            "3. Loan Status",
        )

    choice = parts[0]
    if choice == "1":
        snapshot = await loan_service.run_loan_maintenance_for_user(
            db=db,
            user_id=user.id,
            allow_auto_deduction=False,
        )
        loan = snapshot.get("loan")
        lines = [
            "Agent Summary",
            f"Float: {_money(getattr(agent, 'float_balance', 0.0))}",
            f"Comm: {_money(getattr(agent, 'commission_balance', 0.0))}",
            f"Sweep: {'On' if bool(getattr(agent, 'loan_auto_deduction_enabled', True)) else 'Off'}",
        ]
        if loan and float(getattr(loan, "remaining_balance", 0.0) or 0.0) > 0.0:
            lines.append(f"Loan: {_money(getattr(loan, 'remaining_balance', 0.0))}")
        else:
            lines.append("Loan: None")
        return _submenu(*lines)

    if choice == "2":
        current_state = "On" if bool(getattr(agent, "loan_auto_deduction_enabled", True)) else "Off"
        if len(parts) == 1:
            return _submenu(
                "Loan Sweep",
                f"Current: {current_state}",
                "1. Turn On",
                "2. Turn Off",
            )

        selected = parts[1]
        if selected not in {"1", "2"}:
            return _submenu(
                "Loan Sweep",
                f"Current: {current_state}",
                "1. Turn On",
                "2. Turn Off",
            )

        new_state = selected == "1"
        agent.loan_auto_deduction_enabled = new_state
        db.add(agent)
        await db.commit()
        await db.refresh(agent)
        return _submenu(
            "Loan Sweep Updated",
            f"State: {'On' if new_state else 'Off'}",
        )

    if choice == "3":
        snapshot = await loan_service.run_loan_maintenance_for_user(
            db=db,
            user_id=user.id,
            allow_auto_deduction=False,
        )
        loan = snapshot.get("loan")
        if not loan:
            return _submenu("Loan Status", "No active loan.")

        due_date = getattr(loan, "repayment_due_date", None)
        due_text = due_date.date().isoformat() if due_date else ""
        lines = [
            "Loan Status",
            f"Bal: {_money(getattr(loan, 'remaining_balance', 0.0))}",
            f"State: {str(getattr(loan, 'status', '') or '').title() or 'Open'}",
        ]
        if due_text:
            lines.append(f"By: {due_text}")
        return _submenu(*lines)

    return _submenu(
        "Agent",
        "1. Summary",
        "2. Loan Sweep",
        "3. Loan Status",
    )


async def _handle_transfer(
    db: AsyncSession,
    transaction_engine: TransactionEngine,
    user: models.User,
    agent: models.Agent | None,
    *,
    session_id: str,
    phone_number: str,
    parts: list[str],
) -> str:
    if len(parts) == 0:
        return _submenu("Send/Transfer", "Recipient number:")
    if len(parts) == 1:
        return _submenu("Send/Transfer", "Amount (GHS):")
    if len(parts) == 2:
        return _submenu("Send/Transfer", "Enter PIN:")

    recipient_phone = _parse_phone(parts[0])
    amount = _parse_amount(parts[1])
    pin = parts[2]

    if not _verify_access_pin(user, agent, pin):
        raise ValueError("Invalid PIN.")

    result = await db.execute(
        select(models.User).filter(
            or_(
                models.User.momo_number == recipient_phone,
                models.User.phone_number == recipient_phone,
            )
        )
    )
    recipient = result.scalars().first()
    if not recipient or not recipient.is_active or not recipient.is_verified:
        raise ValueError("Recipient not found.")
    if recipient.id == user.id:
        raise ValueError("Cannot send to yourself.")

    await _ensure_wallet(db, recipient.id)

    sent_today = await _resolve_p2p_total_sent_today(db, user.id)
    free_remaining = max(0.0, round(P2P_DAILY_FREE_LIMIT_GHS - sent_today, 2))
    feeable_amount = max(0.0, round(amount - free_remaining, 2))
    transfer_fee = round(feeable_amount * P2P_TRANSFER_FEE_RATE, 2)

    tx = await transaction_engine.process_transaction(
        user_id=user.id,
        transaction_type=TransactionType.TRANSFER,
        amount=amount,
        metadata={
            **_security_context(user, session_id, phone_number),
            "receiver_id": recipient.id,
            "recipient_wallet_id": recipient_phone,
            "direction": "send",
            "transfer_kind": "wallet_transfer",
            "transferred_amount": amount,
            "transfer_fee": transfer_fee,
            "fee": transfer_fee,
        },
    )

    result = await db.execute(select(models.Wallet).filter(models.Wallet.user_id == user.id))
    sender_wallet = result.scalars().first()

    return _submenu(
        "Transfer OK",
        f"To: {recipient_phone}",
        f"Ref: TRX-{tx.id}",
        f"Bal: {_money(getattr(sender_wallet, 'balance', 0.0))}",
    )


async def _handle_withdraw(
    db: AsyncSession,
    transaction_engine: TransactionEngine,
    user: models.User,
    agent: models.Agent | None,
    *,
    session_id: str,
    phone_number: str,
    parts: list[str],
) -> str:
    if len(parts) == 0:
        return _submenu("Withdraw", "Agent number:")
    if len(parts) == 1:
        return _submenu("Withdraw", "Amount (GHS):")
    if len(parts) == 2:
        return _submenu("Withdraw", "Enter PIN:")

    agent_phone = _parse_phone(parts[0])
    amount = _parse_amount(parts[1])
    pin = parts[2]

    if not _verify_access_pin(user, agent, pin):
        raise ValueError("Invalid PIN.")

    result = await db.execute(
        select(models.User).filter(
            or_(
                models.User.momo_number == agent_phone,
                models.User.phone_number == agent_phone,
            )
        )
    )
    agent_user = result.scalars().first()
    if not agent_user or not agent_user.is_active or not agent_user.is_verified:
        raise ValueError("Agent not found.")

    agent_result = await db.execute(
        select(models.Agent).filter(
            models.Agent.user_id == agent_user.id,
            models.Agent.status == "active",
        )
    )
    cash_agent = agent_result.scalars().first()
    if not cash_agent:
        raise ValueError("Agent not active.")

    commission_rate = float(getattr(cash_agent, "commission_rate", 0.0) or 0.0)
    commission = round(amount * commission_rate, 2)

    tx = await transaction_engine.process_transaction(
        user_id=user.id,
        transaction_type=TransactionType.AGENT_WITHDRAWAL,
        amount=amount,
        agent_id=cash_agent.id,
        metadata={
            **_security_context(user, session_id, phone_number),
            "fee": round(amount * WITHDRAW_FEE_RATE, 2),
            "commission": commission,
        },
    )

    result = await db.execute(select(models.Wallet).filter(models.Wallet.user_id == user.id))
    sender_wallet = result.scalars().first()

    return _submenu(
        "Withdraw OK",
        f"Agent: {agent_phone}",
        f"Ref: TRX-{tx.id}",
        f"Bal: {_money(getattr(sender_wallet, 'balance', 0.0))}",
    )


async def _handle_recharge(
    db: AsyncSession,
    transaction_engine: TransactionEngine,
    user: models.User,
    agent: models.Agent | None,
    *,
    session_id: str,
    phone_number: str,
    parts: list[str],
) -> str:
    if len(parts) == 0:
        return _submenu("Recharge", "Phone number:")
    if len(parts) == 1:
        return _submenu("Recharge", "Amount (GHS):")
    if len(parts) == 2:
        return _submenu("Recharge", "Enter PIN:")

    target_phone = _parse_phone(parts[0])
    amount = _parse_amount(parts[1])
    pin = parts[2]

    if not _verify_access_pin(user, agent, pin):
        raise ValueError("Invalid PIN.")

    network = detect_network(target_phone)
    if network == "UNKNOWN":
        raise ValueError("Enter a valid Ghana mobile number.")

    provider_response = await momo_service.initiate_airtime_payment(
        phone_number=target_phone,
        amount=amount,
        currency="GHS",
        network_provider=network,
        user_id=user.id,
    )
    provider_status = str(provider_response.get("status", "") or "").strip().lower()
    if provider_status not in {"successful", "success", "completed", "pending"}:
        raise ValueError(str(provider_response.get("message") or "Recharge failed."))

    tx = await transaction_engine.process_transaction(
        user_id=user.id,
        transaction_type=TransactionType.AIRTIME,
        amount=amount,
        metadata={
            **_security_context(user, session_id, phone_number),
            "network": network,
            "phone_number": target_phone,
            "provider": "momo",
            "provider_reference": provider_response.get("processor_transaction_id"),
            "cost_price": round(amount * 0.95, 2),
        },
    )

    result = await db.execute(select(models.Wallet).filter(models.Wallet.user_id == user.id))
    sender_wallet = result.scalars().first()

    return _submenu(
        "Recharge OK",
        f"Net: {network}",
        f"Ref: TRX-{tx.id}",
        f"Bal: {_money(getattr(sender_wallet, 'balance', 0.0))}",
    )


async def _handle_escrow(
    db: AsyncSession,
    transaction_engine: TransactionEngine,
    user: models.User,
    agent: models.Agent | None,
    *,
    session_id: str,
    phone_number: str,
    parts: list[str],
) -> str:
    if len(parts) == 0:
        return _submenu("Escrow", "Recipient number:")
    if len(parts) == 1:
        return _submenu("Escrow", "Amount (GHS):")
    if len(parts) == 2:
        return _submenu("Escrow", "Enter PIN:")

    recipient_phone = _parse_phone(parts[0])
    amount = _parse_amount(parts[1])
    pin = parts[2]

    if not _verify_access_pin(user, agent, pin):
        raise ValueError("Invalid PIN.")

    result = await db.execute(
        select(models.User).filter(
            or_(
                models.User.momo_number == recipient_phone,
                models.User.phone_number == recipient_phone,
            )
        )
    )
    recipient = result.scalars().first()
    if not recipient or not recipient.is_active or not recipient.is_verified:
        raise ValueError("Recipient not found.")

    resolved_recipient_number = normalize_ghana_number(
        str(recipient.momo_number or recipient.phone_number or recipient_phone)
    )

    tx = await transaction_engine.process_transaction(
        user_id=user.id,
        transaction_type=TransactionType.ESCROW_CREATE,
        amount=amount,
        metadata={
            **_security_context(user, session_id, phone_number),
            "recipient_id": recipient.id,
            "recipient_wallet_id": resolved_recipient_number,
            "description": "USSD escrow",
            "fee": ESCROW_CREATE_FEE_GHS,
            "release_fee": ESCROW_RELEASE_FEE_GHS,
            "receiver_net_amount": max(amount - ESCROW_RELEASE_FEE_GHS, 0.0),
            "deal_status": "active",
            "deal_created_at": datetime.utcnow().isoformat(),
            "escrow_fee_currency": "GHS",
        },
    )

    result = await db.execute(select(models.Wallet).filter(models.Wallet.user_id == user.id))
    sender_wallet = result.scalars().first()

    return _submenu(
        "Escrow OK",
        f"Ref: TRX-{tx.id}",
        f"Bal: {_money(getattr(sender_wallet, 'balance', 0.0))}",
    )


def _investment_projection(amount: float, duration_days: int) -> tuple[float, float, float]:
    gross_profit = round(
        float(amount) * (INVESTMENT_RISK_FREE_ANNUAL_RATE / 100.0) * (float(duration_days) / 365.0),
        2,
    )
    profit_fee = round(max(gross_profit, 0.0) * INVESTMENT_PROFIT_FEE_RATE, 2)
    net_profit = round(max(gross_profit - profit_fee, 0.0), 2)
    return gross_profit, profit_fee, net_profit


async def _handle_invest(
    db: AsyncSession,
    transaction_engine: TransactionEngine,
    user: models.User,
    agent: models.Agent | None,
    *,
    session_id: str,
    phone_number: str,
    parts: list[str],
) -> str:
    if len(parts) == 0:
        return _submenu("Invest", "Amount (GHS):")
    if len(parts) == 1:
        return _submenu("Invest", "Days (7/14/30/60/90/180/365):")
    if len(parts) == 2:
        return _submenu("Invest", "Enter PIN:")

    amount = _parse_amount(parts[0])
    duration_days = _parse_days(parts[1])
    pin = parts[2]

    if amount < INVESTMENT_MIN_AMOUNT_GHS:
        raise ValueError(f"Minimum investment amount is {_money(INVESTMENT_MIN_AMOUNT_GHS)}.")
    if duration_days not in INVESTMENT_ALLOWED_DURATIONS_DAYS:
        allowed = "/".join(str(item) for item in INVESTMENT_ALLOWED_DURATIONS_DAYS)
        raise ValueError(f"Choose {allowed}.")
    if not _verify_access_pin(user, agent, pin):
        raise ValueError("Invalid PIN.")

    gross_profit, profit_fee, net_profit = _investment_projection(amount, duration_days)

    tx = await transaction_engine.process_transaction(
        user_id=user.id,
        transaction_type=TransactionType.INVESTMENT_CREATE,
        amount=amount,
        metadata={
            **_security_context(user, session_id, phone_number),
            "plan_name": f"USSD {duration_days}D Plan",
            "duration_days": duration_days,
            "expected_rate": INVESTMENT_RISK_FREE_ANNUAL_RATE,
            "projected_gross_profit": gross_profit,
            "projected_profit_fee": profit_fee,
            "projected_net_profit": net_profit,
            "profit_fee_rate": INVESTMENT_PROFIT_FEE_RATE,
            "investment_status": "active",
            "investment_created_at": datetime.utcnow().isoformat(),
            "maturity_at": (datetime.utcnow() + timedelta(days=duration_days)).isoformat(),
            "investment_currency": "GHS",
        },
    )

    result = await db.execute(select(models.Wallet).filter(models.Wallet.user_id == user.id))
    sender_wallet = result.scalars().first()

    return _submenu(
        "Invest OK",
        f"Ref: TRX-{tx.id}",
        f"Bal: {_money(getattr(sender_wallet, 'balance', 0.0))}",
    )


async def _handle_loan_apply(
    db: AsyncSession,
    user: models.User,
    agent: models.Agent | None,
    *,
    session_id: str,
    phone_number: str,
    parts: list[str],
    allowed_periods: list[int],
) -> str:
    if len(parts) == 0:
        return _submenu("Loans", "Amount (GHS):")
    if len(parts) == 1:
        allowed_text = "/".join(str(period) for period in allowed_periods)
        return _submenu("Loans", f"Days ({allowed_text}):")
    if len(parts) == 2:
        return _submenu("Loans", "Enter PIN:")

    amount = _parse_amount(parts[0])
    duration_days = _parse_days(parts[1])
    pin = parts[2]

    if duration_days not in allowed_periods:
        allowed_text = "/".join(str(period) for period in allowed_periods)
        raise ValueError(f"Choose {allowed_text}.")
    if not _verify_access_pin(user, agent, pin):
        raise ValueError("Invalid PIN.")

    application = LoanApplicationCreate(
        amount=amount,
        repayment_duration=duration_days,
        purpose=f"USSD loan via {USSD_SHORTCODE}",
    )

    transaction_metadata = _security_context(
        user,
        session_id,
        phone_number,
        daily_limit=max(float(user.daily_limit or 0.0), float(amount)),
    )
    loan_application = await loan_service.create_self_service_loan(
        db=db,
        user=user,
        application=application,
        transaction_metadata=transaction_metadata,
    )

    snapshot = await loan_service.run_loan_maintenance_for_user(
        db=db,
        user_id=user.id,
        allow_auto_deduction=False,
    )
    loan = snapshot.get("loan")

    due_text = ""
    if loan and getattr(loan, "repayment_due_date", None):
        due_text = loan.repayment_due_date.date().isoformat()

    lines = ["Loan OK", f"Ref: L{loan.id if loan else loan_application.id}"]
    if due_text:
        lines.append(f"Due: {due_text}")
    return _submenu(*lines)


async def _handle_loan_status(
    db: AsyncSession,
    user: models.User,
    agent: models.Agent | None,
    *,
    session_id: str,
    phone_number: str,
    parts: list[str],
) -> str:
    if len(parts) == 0:
        return _submenu("Loans", "Enter PIN:")

    pin = parts[0]
    if not _verify_access_pin(user, agent, pin):
        raise ValueError("Invalid PIN.")

    snapshot = await loan_service.run_loan_maintenance_for_user(
        db=db,
        user_id=user.id,
        allow_auto_deduction=False,
    )
    loan = snapshot.get("loan")
    if not loan:
        return _submenu("No active loan.")

    due_date = getattr(loan, "repayment_due_date", None)
    due_text = due_date.date().isoformat() if due_date else ""

    lines = [
        "Loan",
        f"Due: {_money(getattr(loan, 'remaining_balance', 0.0))}",
        f"Status: {str(getattr(loan, 'status', '') or '').title() or 'Open'}",
    ]
    if due_text:
        lines.append(f"By: {due_text}")
    return _submenu(*lines)


@router.post("/ussd", response_class=PlainTextResponse)
async def ussd_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
    transaction_engine: TransactionEngine = Depends(get_transaction_engine),
):
    """
    Cyber Cash USSD gateway.
    The menu is keyed to *360# and supports Ghana-wide registered users and agents.
    """
    try:
        form = await request.form()
        raw_phone_number = (
            form.get("phoneNumber")
            or form.get("phone_number")
            or form.get("msisdn")
            or form.get("caller")
            or ""
        )
        session_id = str(
            form.get("sessionId")
            or form.get("session_id")
            or form.get("session")
            or ""
        ).strip()
        service_code = str(
            form.get("serviceCode")
            or form.get("service_code")
            or form.get("shortCode")
            or ""
        ).strip()
        text = str(form.get("text") or form.get("ussdString") or "").strip()
        inputs = [part.strip() for part in text.split("*")] if text else []

        expected_shortcode = _normalize_shortcode(USSD_SHORTCODE)
        received_shortcode = _normalize_shortcode(service_code)
        if received_shortcode and received_shortcode != expected_shortcode:
            logger.info("USSD callback received on service code %s instead of %s", service_code, USSD_SHORTCODE)

        user, wallet, agent = await _resolve_user_context(db, raw_phone_number)
        if not user:
            return _end("Cyber Cash account not found.")
        if not user.is_active or not user.is_verified:
            return _end("Account not active.")

        if not inputs or _back_requested(inputs):
            return _main_menu(agent)

        if inputs[0] == "1":
            if len(inputs) == 1:
                return _submenu("Balance", "Enter PIN:")
            if not _verify_access_pin(user, agent, inputs[1]):
                raise ValueError("Invalid PIN.")
            return await _render_balance_menu(
                db,
                user,
                agent,
                session_id=session_id,
                phone_number=raw_phone_number,
            )

        loan_policy = await loan_service.get_loan_policy_for_user(db=db, user=user)
        allowed_periods = [int(period) for period in loan_policy.get("allowed_periods", [1, 7, 14, 30])]

        if inputs[0] == "2":
            return await _handle_transfer(
                db,
                transaction_engine,
                user,
                agent,
                session_id=session_id,
                phone_number=raw_phone_number,
                parts=inputs[1:],
            )

        if inputs[0] == "3":
            return await _handle_withdraw(
                db,
                transaction_engine,
                user,
                agent,
                session_id=session_id,
                phone_number=raw_phone_number,
                parts=inputs[1:],
            )

        if inputs[0] == "4":
            return await _handle_recharge(
                db,
                transaction_engine,
                user,
                agent,
                session_id=session_id,
                phone_number=raw_phone_number,
                parts=inputs[1:],
            )

        if inputs[0] == "5":
            return await _handle_escrow(
                db,
                transaction_engine,
                user,
                agent,
                session_id=session_id,
                phone_number=raw_phone_number,
                parts=inputs[1:],
            )

        if inputs[0] == "6":
            return await _handle_invest(
                db,
                transaction_engine,
                user,
                agent,
                session_id=session_id,
                phone_number=raw_phone_number,
                parts=inputs[1:],
            )

        if inputs[0] == "7":
            if len(inputs) == 1:
                return _submenu(
                    "Loans",
                    "1. Apply",
                    "2. Status",
                )
            if inputs[1] == "1":
                return await _handle_loan_apply(
                    db,
                    user,
                    agent,
                    session_id=session_id,
                    phone_number=raw_phone_number,
                    parts=inputs[2:],
                    allowed_periods=allowed_periods,
                )
            if inputs[1] == "2":
                return await _handle_loan_status(
                    db,
                    user,
                    agent,
                    session_id=session_id,
                    phone_number=raw_phone_number,
                    parts=inputs[2:],
                )
            return _submenu(
                "Loans",
                "1. Apply",
                "2. Status",
            )

        if inputs[0] == "8":
            return await _render_btc_balance_menu(
                db,
                user,
                session_id=session_id,
                phone_number=raw_phone_number,
            )

        if inputs[0] == "9" and agent:
            return await _render_agent_shortcut_menu(
                db,
                user,
                agent,
                session_id=session_id,
                phone_number=raw_phone_number,
                parts=inputs[1:],
            )

        return _main_menu(agent)

    except ValueError as exc:
        logger.warning("USSD validation error: %s", exc)
        return _end(str(exc))
    except Exception as exc:
        logger.exception("USSD error: %s", exc)
        return _end("Application error.")
