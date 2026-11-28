import asyncio
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import json
from typing import List

from fastapi import APIRouter, Depends, Header, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import or_, select
from backend.database import AsyncSessionLocal, get_db
from backend.models import Agent, User, Wallet, Transaction, UserNotification
from backend.dependencies.auth import get_current_user
from backend.core.security import ALGORITHM, SECRET_KEY
from jose import JWTError, jwt
from utils.network import normalize_ghana_number
from backend.schemas.wallet import (
    TransferFundsRequest,
    TransferFundsResponse,
    WalletResponse,
    InvestmentReinvestToggleRequest,
    InvestmentReinvestToggleResponse,
)
from backend.schemas.fx import ExchangeRequest, ExchangeResponse # New Import
from backend.services.ledger_service import LedgerService, get_ledger_service
from backend.services.fx_service import FxService, get_fx_service # New Import
from backend.services import loan_service
from backend.services.notification import NotificationService
from backend.services.reconciliation_service import verify_wallet_balance, log_wallet_audit, get_audit_logs_for_user
from backend.core.transaction_types import TransactionType

router = APIRouter(prefix="/wallet", tags=["Wallet"])
ALLOWED_SOURCE_BALANCES = {
    "balance": "Main Balance",
    "escrow_balance": "Escrow Balance",
    "loan_balance": "Loan Balance",
    "investment_balance": "Investment Balance",
}
MIN_TRANSFER_AMOUNT_GHS = Decimal("1.00")
WITHDRAW_TO_AGENT_FEE_RATE = Decimal("0.01")
P2P_TRANSFER_FEE_RATE = Decimal("0.005")
P2P_DAILY_FREE_LIMIT_GHS = Decimal("100.00")


def _safe_load_metadata(metadata_json: str | None) -> dict:
    if not metadata_json:
        return {}
    try:
        value = json.loads(metadata_json)
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _transaction_party_label(user: User) -> str:
    name = " ".join(str(getattr(user, "full_name", "") or "").split()) or "CyberCash user"
    number = str(getattr(user, "momo_number", "") or getattr(user, "phone_number", "") or "").strip()
    return f"{name} ({number})" if number else name


async def _resolve_p2p_total_sent_today(db: AsyncSession, *, user_id: int) -> Decimal:
    now = datetime.now(timezone.utc)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)

    result = await db.execute(
        select(Transaction).filter(
            Transaction.user_id == user_id,
            Transaction.type == TransactionType.TRANSFER,
            Transaction.status == "completed",
            Transaction.timestamp >= day_start,
            Transaction.timestamp < day_end,
        )
    )
    transactions = result.scalars().all()

    total_sent = Decimal("0.00")
    for tx in transactions:
        metadata = _safe_load_metadata(tx.metadata_json)
        if str(metadata.get("direction", "")).lower() != "send":
            continue
        if str(metadata.get("transfer_kind", "")).lower() != "wallet_transfer":
            continue

        transferred_amount = metadata.get("transferred_amount")
        if transferred_amount is None:
            transferred_amount = abs(Decimal(str(tx.amount or "0.00")))
            fee = Decimal(str(metadata.get("transfer_fee", "0.00")))
            transferred_amount = max(Decimal("0.00"), transferred_amount - fee)
        total_sent += Decimal(str(transferred_amount or "0.00"))

    return total_sent.quantize(Decimal("0.01"))


def _tx_to_dict(
    t: Transaction,
    user: User | None = None,
    *,
    sender_name: str = "",
    receiver_name: str = "",
    sender_number: str = "",
    receiver_number: str = "",
) -> dict:
    timestamp = t.timestamp
    if timestamp and timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    metadata = _safe_load_metadata(t.metadata_json)
    reference = str(
        t.provider_reference
        or metadata.get("reference")
        or metadata.get("provider_reference")
        or metadata.get("payment_reference")
        or ""
    ).strip()
    direction = str(metadata.get("direction") or t.entry_type or "").strip().lower()
    counterparty_name = receiver_name if direction in {"send", "debit", "out", "outgoing"} else sender_name
    counterparty_role = "Receiver" if direction in {"send", "debit", "out", "outgoing"} else "Sender"
    description = ""
    if str(t.type or "").strip().upper() == str(TransactionType.TRANSFER).upper():
        if counterparty_name:
            description = f"{'Sent to' if counterparty_role == 'Receiver' else 'Received from'} {counterparty_name}"
        else:
            description = f"{'Sent to' if counterparty_role == 'Receiver' else 'Received from'} a CyberCash user"
    return {
        "id": t.id,
        "type": t.type,
        "amount": t.amount,
        "direction": t.entry_type,
        "currency": t.currency,
        "status": t.status,
        "timestamp": timestamp.isoformat() if timestamp else datetime.now(timezone.utc).isoformat(),
        "reference": reference,
        "username": str(getattr(user, "full_name", "") or "").strip(),
        "momo_number": str(getattr(user, "momo_number", "") or getattr(user, "phone_number", "") or "").strip(),
        "sender_name": sender_name,
        "receiver_name": receiver_name,
        "sender_number": sender_number,
        "receiver_number": receiver_number,
        "counterparty_name": counterparty_name,
        "counterparty_role": counterparty_role,
        "description": description,
    }


async def _transaction_counterparty_names(
    db: AsyncSession,
    transactions: list[Transaction],
    current_user: User,
) -> dict[int, tuple[str, str, str, str]]:
    """Resolve transfer parties for the authenticated transaction participants only."""
    details: dict[int, dict] = {}
    counterpart_ids: set[int] = set()
    counterpart_numbers: set[str] = set()
    for transaction in transactions:
        if str(transaction.type or "").strip().upper() != str(TransactionType.TRANSFER).upper():
            continue
        metadata = _safe_load_metadata(transaction.metadata_json)
        direction = str(metadata.get("direction") or transaction.entry_type or "").strip().lower()
        receiving = direction in {"receive", "credit", "in", "incoming", "received"}
        name_key = "sender_name" if receiving else "recipient_name"
        id_key = "sender_user_id" if receiving else "recipient_user_id"
        number_key = "sender_wallet_id" if receiving else "recipient_wallet_id"
        counterpart_id = metadata.get(id_key)
        try:
            if counterpart_id is not None:
                counterpart_ids.add(int(counterpart_id))
        except (TypeError, ValueError):
            pass
        number = str(metadata.get(number_key) or "").strip()
        if number:
            counterpart_numbers.add(number)
        details[int(transaction.id)] = {
            "direction": "receive" if receiving else "send",
            "name": str(metadata.get(name_key) or "").strip(),
            "id": counterpart_id,
            "number": number,
        }

    users_by_id: dict[int, User] = {}
    users_by_number: dict[str, User] = {}
    clauses = []
    if counterpart_ids:
        clauses.append(User.id.in_(counterpart_ids))
    if counterpart_numbers:
        clauses.extend((User.phone_number.in_(counterpart_numbers), User.momo_number.in_(counterpart_numbers)))
    if clauses:
        result = await db.execute(select(User).where(or_(*clauses)))
        for candidate in result.scalars().all():
            users_by_id[int(candidate.id)] = candidate
            for number in (candidate.phone_number, candidate.momo_number):
                if number:
                    users_by_number[str(number).strip()] = candidate

    names: dict[int, tuple[str, str, str, str]] = {}
    own_name = str(getattr(current_user, "full_name", "") or "").strip()
    own_number = str(
        getattr(current_user, "momo_number", "") or getattr(current_user, "phone_number", "") or ""
    ).strip()
    for transaction_id, detail in details.items():
        candidate = None
        try:
            candidate = users_by_id.get(int(detail["id"])) if detail["id"] is not None else None
        except (TypeError, ValueError):
            candidate = None
        candidate = candidate or users_by_number.get(detail["number"])
        counterpart_name = detail["name"] or str(getattr(candidate, "full_name", "") or "").strip()
        counterpart_number = str(
            getattr(candidate, "momo_number", "") or getattr(candidate, "phone_number", "") or ""
        ).strip()
        if detail["direction"] == "receive":
            names[transaction_id] = (counterpart_name, own_name, counterpart_number, own_number)
        else:
            names[transaction_id] = (own_name, counterpart_name, own_number, counterpart_number)
    return names


async def _p2p_transfer_replay(db: AsyncSession, *, user_id: int, idempotency_key: str):
    """Return the original success payload when a client safely retries a transfer."""
    result = await db.execute(
        select(Transaction).filter(
            Transaction.user_id == user_id,
            Transaction.idempotency_key == idempotency_key,
            Transaction.type == TransactionType.TRANSFER,
            Transaction.status == "completed",
        )
    )
    transaction = result.scalars().first()
    if transaction is None:
        return None
    wallet_result = await db.execute(select(Wallet).filter(Wallet.user_id == user_id))
    wallet = wallet_result.scalars().first()
    if wallet is None:
        return None
    metadata = _safe_load_metadata(transaction.metadata_json)
    return {
        "id": wallet.id,
        "user_id": wallet.user_id,
        "currency": wallet.currency,
        "balance": float(wallet.balance or 0.0),
        "escrow_balance": float(wallet.escrow_balance or 0.0),
        "loan_balance": float(wallet.loan_balance or 0.0),
        "investment_balance": float(wallet.investment_balance or 0.0),
        "created_at": wallet.created_at,
        "updated_at": wallet.updated_at,
        "metadata_json": wallet.metadata_json,
        "transfer_reference": f"TRX-{int(transaction.id)}",
        "recipient_wallet_id": str(metadata.get("recipient_wallet_id") or ""),
        "source_balance": str(metadata.get("source_balance") or "balance"),
        "recipient_is_agent": bool(metadata.get("recipient_must_be_agent", False)),
        "transfer_fee": float(metadata.get("transfer_fee") or 0.0),
        "transfer_fee_rate": float(metadata.get("transfer_fee_rate") or 0.0),
        "total_debited": float(metadata.get("total_debited") or abs(float(transaction.amount or 0.0))),
        "p2p_daily_free_limit": float(metadata.get("p2p_daily_free_limit") or 0.0),
        "p2p_total_sent_today_before": float(metadata.get("p2p_total_sent_today_before") or 0.0),
        "p2p_free_remaining_before": float(metadata.get("p2p_free_remaining_before") or 0.0),
        "p2p_fee_free_amount": float(metadata.get("p2p_fee_free_amount") or 0.0),
        "p2p_feeable_amount": float(metadata.get("p2p_feeable_amount") or 0.0),
    }


async def _resolve_ws_user(token: str) -> User | None:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        identity = payload.get("sub")
        if not identity:
            return None
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(User).filter((User.email == identity) | (User.phone_number == identity))
            )
            return result.scalars().first()
    except JWTError:
        return None
    except Exception:
        return None

@router.get("/")
def wallet_status():
    return {"wallet": "ready"}

@router.get("/verify", response_model=dict)
async def verify_wallet(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Verify wallet balance against the transaction ledger.
    
    Returns the wallet balance, ledger-calculated balance, and verification status.
    This is the recommended way to trust wallet balance after updates, logouts, or long inactivity.
    
    Response:
    {
        "wallet_balance": 500.00,
        "ledger_balance": 500.00,
        "status": "verified" | "mismatch",
        "difference": 0.00,
        "verified_at": "2026-06-04T12:00:00Z"
    }
    """
    try:
        is_verified, details = await verify_wallet_balance(db, current_user.id)
        return details # This already returns the required dictionary with comparison details
    finally:
        await db.close()


@router.get("/audit-logs", response_model=list)
async def get_wallet_audit_logs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(100, ge=1, le=500),
):
    """
    Retrieve audit logs for the current user's wallet.
    Shows all balance changes, transfers, and transactions.
    """
    try:
        logs = await get_audit_logs_for_user(db, current_user.id, limit=limit)
        return [
            {
                "id": log.id,
                "action": log.action,
                "description": log.description,
                "before_balance": log.before_balance,
                "after_balance": log.after_balance,
                "amount_changed": log.amount_changed,
                "transaction_id": log.transaction_id,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ]
    finally:
        await db.close()

@router.get("/all_fiat", response_model=List[WalletResponse])
async def read_all_user_fiat_wallets( # Added async
    db: AsyncSession = Depends(get_db), # Changed type hint
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve all fiat wallets for the current authenticated user.
    """
    try:
        result = await db.execute(select(Wallet).filter(Wallet.user_id == current_user.id))
        wallets = result.scalars().all()
        # Filter for fiat currencies, assuming crypto wallets are separate
        # For now, return all wallets as `Wallet` model implicitly represents fiat wallets.
        # If crypto wallets are also stored in `Wallet` table, then a `is_fiat` field
        # or similar categorization would be needed in the Wallet model.
        return wallets
    finally:
        await db.close()

@router.post("/exchange", response_model=ExchangeResponse)
async def exchange_currency(
    request: ExchangeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    fx_service: FxService = Depends(get_fx_service)
):
    """
    Allows a user to exchange one currency for another.
    """
    try:
        if request.amount <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Exchange amount must be positive.")
        
        transaction_details = await fx_service.perform_exchange( # Now returns a dictionary
            user=current_user,
            from_currency=request.from_currency,
            to_currency=request.to_currency,
            amount=request.amount
        )
        
        return ExchangeResponse(**transaction_details) # Unpack the dictionary directly
    finally:
        await db.close()


@router.get("/p2p/fee-status")
async def get_p2p_fee_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the sender's remaining daily free P2P transfer allowance (GHS)."""
    try:
        total_sent_today = await _resolve_p2p_total_sent_today(db, user_id=current_user.id)
        free_remaining = max(Decimal("0.00"), P2P_DAILY_FREE_LIMIT_GHS - total_sent_today)
        return {
            "p2p_daily_free_limit": P2P_DAILY_FREE_LIMIT_GHS,
            "p2p_total_sent_today": total_sent_today,
            "p2p_free_remaining": free_remaining,
            "p2p_fee_rate": P2P_TRANSFER_FEE_RATE,
        }
    finally:
        await db.close()


@router.post("/transfer", response_model=TransferFundsResponse)
async def transfer_funds(
    request: TransferFundsRequest,
    db: AsyncSession = Depends(get_db), # Changed type hint
    current_user: User = Depends(get_current_user),
    ledger_service: LedgerService = Depends(get_ledger_service),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    try:
        transfer_idempotency_key = str(idempotency_key or "").strip()
        if len(transfer_idempotency_key) > 128:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid transfer request. Please try again.")
        if transfer_idempotency_key:
            replay = await _p2p_transfer_replay(db, user_id=current_user.id, idempotency_key=transfer_idempotency_key)
            if replay is not None:
                return replay

        is_agent_withdraw = bool(request.recipient_must_be_agent)
        if request.amount <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Transfer amount must be positive.")
        if request.amount < MIN_TRANSFER_AMOUNT_GHS:
            min_amount_text = f"{MIN_TRANSFER_AMOUNT_GHS:.2f}"
            if is_agent_withdraw:
                detail = f"Minimum withdrawal amount is GHS {min_amount_text}."
            else:
                detail = f"Minimum P2P transfer amount is GHS {min_amount_text}."
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

        requested_amount = Decimal(str(request.amount)).quantize(Decimal("0.01"))
        fee_rate = WITHDRAW_TO_AGENT_FEE_RATE if is_agent_withdraw else P2P_TRANSFER_FEE_RATE

        p2p_total_sent_today_before = Decimal("0.00")
        p2p_free_remaining_before = Decimal("0.00")
        p2p_fee_free_amount = Decimal("0.00")
        p2p_feeable_amount = requested_amount

        if not is_agent_withdraw:
            p2p_total_sent_today_before = await _resolve_p2p_total_sent_today(db, user_id=current_user.id)
            p2p_free_remaining_before = max(Decimal("0.00"), P2P_DAILY_FREE_LIMIT_GHS - p2p_total_sent_today_before)
            p2p_fee_free_amount = min(requested_amount, p2p_free_remaining_before)
            p2p_feeable_amount = max(Decimal("0.00"), requested_amount - p2p_free_remaining_before)

        transfer_fee = (p2p_feeable_amount * fee_rate).quantize(Decimal("0.01"))
        total_debited = requested_amount + transfer_fee

        # Recipient resolution
        recipient_wallet_id = normalize_ghana_number(request.recipient_wallet_id or "").strip()
        if not recipient_wallet_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="recipient_wallet_id is required.")

        result = await db.execute(
            select(User).filter(
                (User.momo_number == recipient_wallet_id) | (User.phone_number == recipient_wallet_id)
            )
        )
        recipient_user = result.scalars().first()
        if not recipient_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipient user not found.")
        if recipient_user.id == current_user.id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot transfer funds to yourself.")

        # Point 1: Ensure exactly one wallet per user - check before creation
        res = await db.execute(select(Wallet).filter(Wallet.user_id == recipient_user.id))
        recipient_wallet = res.scalars().first()
        if not recipient_wallet:
            # This should ideally not happen if wallet is created with user.
            # If it does, it's a data integrity issue.
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Recipient wallet not found.")

        # 2. Lock both wallets using consistent ordering (by user_id) to prevent deadlocks
        target_user_ids = sorted([current_user.id, recipient_user.id])
        stmt = (
            select(Wallet)
            .filter(Wallet.user_id.in_(target_user_ids))
            .order_by(Wallet.user_id)
            .with_for_update()
        )
        res = await db.execute(stmt)
        wallets = res.scalars().all()
        
        sender_wallet = next((w for w in wallets if w.user_id == current_user.id), None)
        recipient_wallet = next((w for w in wallets if w.user_id == recipient_user.id), None)

        # Recheck after acquiring the sender wallet lock. A concurrent retry may
        # have committed while this request waited for the lock.
        if transfer_idempotency_key:
            replay = await _p2p_transfer_replay(db, user_id=current_user.id, idempotency_key=transfer_idempotency_key)
            if replay is not None:
                return replay

        # Sender's wallet
        if not sender_wallet:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sender's wallet not found.")
        
        if sender_wallet.is_frozen:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Sender's wallet is currently frozen by administration."
            )

        source_balance_key = str(request.source_balance or "balance").strip().lower()
        if source_balance_key not in ALLOWED_SOURCE_BALANCES:
            allowed = ", ".join(ALLOWED_SOURCE_BALANCES.keys())
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid source_balance. Allowed values: {allowed}.",
            )

        if source_balance_key == "investment_balance":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Investment funds are locked until maturity. "
                    "Claim matured principal and profit from Investment Center."
                ),
            )

        sender_source_balance = Decimal(str(getattr(sender_wallet, source_balance_key, "0.00")))
        required_amount = total_debited
        if sender_source_balance < required_amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient balance in {ALLOWED_SOURCE_BALANCES[source_balance_key]}.",
            )

        if is_agent_withdraw:
            agent_result = await db.execute(
                select(Agent).filter(Agent.user_id == recipient_user.id, Agent.status == "active")
            )
            active_agent = agent_result.scalars().first()
            if not active_agent:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Recipient is not an active registered agent.",
                )

        if recipient_wallet.is_frozen:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Recipient's wallet is currently frozen by administration."
            )

        # Atomic transfer operation: wallet updates + transaction logs + ledger in one DB commit.
        sender_before_balance = Decimal(str(sender_wallet.balance))
        recipient_before_balance = Decimal(str(recipient_wallet.balance))

        setattr(sender_wallet, source_balance_key, sender_source_balance - required_amount)
        recipient_wallet.balance += requested_amount
        sender_wallet.version += 1
        recipient_wallet.version += 1

        sender_transaction = Transaction(
            user_id=current_user.id,
            wallet_id=sender_wallet.id,
            type=TransactionType.TRANSFER,
            entry_type="debit",
            amount=-required_amount,
            currency=request.currency,
            status="completed",
            idempotency_key=transfer_idempotency_key or None,
            metadata_json=json.dumps(
                {
                    "direction": "send",
                    "recipient_wallet_id": recipient_user.momo_number or recipient_user.phone_number,
                    "recipient_user_id": recipient_user.id,
                    "recipient_name": str(recipient_user.full_name or "").strip(),
                    "sender_user_id": current_user.id,
                    "sender_name": str(current_user.full_name or "").strip(),
                    "source_balance": source_balance_key,
                    "recipient_must_be_agent": is_agent_withdraw,
                    "transfer_kind": "withdraw_to_agent" if is_agent_withdraw else "wallet_transfer",
                    "transferred_amount": requested_amount,
                    "transfer_fee": transfer_fee,
                    "transfer_fee_rate": fee_rate,
                    "total_debited": required_amount,
                    **(
                        {}
                        if is_agent_withdraw
                        else {
                            "p2p_daily_free_limit": P2P_DAILY_FREE_LIMIT_GHS,
                            "p2p_total_sent_today_before": p2p_total_sent_today_before,
                            "p2p_free_remaining_before": p2p_free_remaining_before,
                            "p2p_fee_free_amount": p2p_fee_free_amount,
                            "p2p_feeable_amount": p2p_feeable_amount,
                        }
                    ),
                },
                default=str,
            ),
        )
        db.add(sender_transaction)
        await db.flush()

        recipient_transaction = Transaction(
            user_id=recipient_user.id,
            wallet_id=recipient_wallet.id,
            type=TransactionType.TRANSFER,
            entry_type="credit",
            amount=requested_amount,
            currency=request.currency,
            status="completed",
            metadata_json=json.dumps(
                {
                    "direction": "receive",
                    "sender_wallet_id": current_user.momo_number or current_user.phone_number,
                    "sender_user_id": current_user.id,
                    "sender_name": str(current_user.full_name or "").strip(),
                    "recipient_user_id": recipient_user.id,
                    "recipient_name": str(recipient_user.full_name or "").strip(),
                    "source_balance": source_balance_key,
                    "transfer_kind": "withdraw_to_agent" if is_agent_withdraw else "wallet_transfer",
                    "transferred_amount": requested_amount,
                    "transfer_fee": transfer_fee,
                    "transfer_fee_rate": fee_rate,
                },
                default=str,
            ),
        )
        db.add(recipient_transaction)
        await db.flush()

        transfer_reference = f"TRX-{int(sender_transaction.id)}"
        sender_party = _transaction_party_label(current_user)
        recipient_party = _transaction_party_label(recipient_user)
        db.add_all(
            [
                UserNotification(
                    user_id=current_user.id,
                    notification_type="transfer_sent",
                    title="Transfer sent",
                    message=(
                        f"Transfer sent: {request.currency.upper()} {requested_amount:.2f} "
                        f"to {recipient_party}. Reference: {transfer_reference}."
                    ),
                    transaction_id=sender_transaction.id,
                    dedupe_key=f"transaction:{sender_transaction.id}:user:{current_user.id}:success",
                ),
                UserNotification(
                    user_id=recipient_user.id,
                    notification_type="transfer_received",
                    title="Transfer received",
                    message=(
                        f"Transfer received: {request.currency.upper()} {requested_amount:.2f} "
                        f"from {sender_party}. Reference: {transfer_reference}."
                    ),
                    transaction_id=recipient_transaction.id,
                    dedupe_key=f"transaction:{recipient_transaction.id}:user:{recipient_user.id}:success",
                ),
            ]
        )

        sender_identifier = current_user.momo_number or current_user.phone_number or f"user:{current_user.id}"
        recipient_identifier = recipient_user.momo_number or recipient_user.phone_number or f"user:{recipient_user.id}"

        ledger_entries_data = [
            {"account_name": "Customer Wallets (Liability)", "debit": float(required_amount), "credit": 0.0},
            {"account_name": "Customer Wallets (Liability)", "debit": 0.0, "credit": float(requested_amount)},
        ]
        if transfer_fee > 0:
            ledger_entries_data.append(
                {"account_name": "Revenue - Transaction Fees", "debit": 0.0, "credit": float(transfer_fee)}
            )

        await ledger_service.create_journal_entry(
            description=f"Funds transfer from {sender_identifier} to {recipient_identifier}",
            ledger_entries_data=ledger_entries_data,
            transaction=sender_transaction,
            auto_commit=False,
        )

        await db.commit()

        # Email delivery is best-effort and must not delay or invalidate the
        # committed transfer. The in-app notices above are already durable.
        notification_service = NotificationService()
        await asyncio.gather(
            notification_service.send_transaction_notification(
                current_user,
                "transfer",
                requested_amount,
                currency=request.currency,
                subject="Transfer sent",
                direction="send",
                sender_name=str(current_user.full_name or "").strip(),
                sender_number=str(current_user.momo_number or current_user.phone_number or "").strip(),
                receiver_name=str(recipient_user.full_name or "").strip(),
                receiver_number=str(recipient_user.momo_number or recipient_user.phone_number or "").strip(),
                idempotency_key=f"transaction:{sender_transaction.id}:user:{current_user.id}:success",
            ),
            notification_service.send_transaction_notification(
                recipient_user,
                "transfer",
                requested_amount,
                currency=request.currency,
                subject="Transfer received",
                direction="receive",
                sender_name=str(current_user.full_name or "").strip(),
                sender_number=str(current_user.momo_number or current_user.phone_number or "").strip(),
                receiver_name=str(recipient_user.full_name or "").strip(),
                receiver_number=str(recipient_user.momo_number or recipient_user.phone_number or "").strip(),
                idempotency_key=f"transaction:{recipient_transaction.id}:user:{recipient_user.id}:success",
            ),
            return_exceptions=True,
        )

        await loan_service.run_loan_maintenance_for_user(
            db=db,
            user_id=recipient_user.id,
            allow_auto_deduction=True,
        )
        
        # Log audit entries for sender and recipient
        sender_after_balance = Decimal(str(sender_wallet.balance))
        recipient_after_balance = Decimal(str(recipient_wallet.balance))
        
        await log_wallet_audit(
            db,
            user_id=current_user.id,
            action="TRANSFER_SENT",
            transaction_id=sender_transaction.id,
            before_balance=sender_before_balance,
            after_balance=sender_after_balance,
            amount_changed=-required_amount,
            description=f"Transfer sent to {recipient_identifier}: {requested_amount} GHS (fee: {transfer_fee} GHS)",
            metadata_json=json.dumps(
                {
                    "recipient_id": recipient_user.id,
                    "recipient_identifier": recipient_identifier,
                    "transferred_amount": requested_amount,
                    "fee": transfer_fee,
                    "transfer_reference": f"TRX-{int(sender_transaction.id)}",
                },
                default=str,
            ),
        )
        
        await log_wallet_audit(
            db,
            user_id=recipient_user.id,
            action="TRANSFER_RECEIVED",
            transaction_id=recipient_transaction.id,
            before_balance=recipient_before_balance,
            after_balance=recipient_after_balance,
            amount_changed=requested_amount,
            description=f"Transfer received from {sender_identifier}: {requested_amount} GHS",
            metadata_json=json.dumps(
                {
                    "sender_id": current_user.id,
                    "sender_identifier": sender_identifier,
                    "transferred_amount": requested_amount,
                    "transfer_reference": f"TRX-{int(sender_transaction.id)}",
                },
                default=str,
            ),
        )
        
        await db.commit()
        await db.refresh(sender_wallet)

        resolved_recipient_number = recipient_user.momo_number or recipient_user.phone_number or recipient_wallet_id
        return {
            "id": sender_wallet.id,
            "user_id": sender_wallet.user_id,
            "currency": sender_wallet.currency,
            "balance": float(sender_wallet.balance or 0.0),
            "escrow_balance": float(sender_wallet.escrow_balance or 0.0),
            "loan_balance": float(sender_wallet.loan_balance or 0.0),
            "investment_balance": float(sender_wallet.investment_balance or 0.0),
            "created_at": sender_wallet.created_at,
            "updated_at": sender_wallet.updated_at,
            "metadata_json": sender_wallet.metadata_json,
            "transfer_reference": transfer_reference,
            "recipient_wallet_id": str(resolved_recipient_number),
            "source_balance": source_balance_key,
            "recipient_is_agent": is_agent_withdraw,
            "transfer_fee": transfer_fee,
            "transfer_fee_rate": fee_rate,
            "total_debited": required_amount,
            "p2p_daily_free_limit": 0.0 if is_agent_withdraw else P2P_DAILY_FREE_LIMIT_GHS,
            "p2p_total_sent_today_before": 0.0 if is_agent_withdraw else p2p_total_sent_today_before,
            "p2p_free_remaining_before": 0.0 if is_agent_withdraw else p2p_free_remaining_before,
            "p2p_fee_free_amount": 0.0 if is_agent_withdraw else p2p_fee_free_amount,
            "p2p_feeable_amount": 0.0 if is_agent_withdraw else p2p_feeable_amount,
        }
    except HTTPException:
        await db.rollback()
        raise
    except Exception:
        await db.rollback()
        raise
    finally:
        await db.close()

@router.get("/me", response_model=WalletResponse)
async def read_user_wallet( # Added async
    db: AsyncSession = Depends(get_db), # Changed type hint
    current_user: User = Depends(get_current_user)
):
    try:
        # Read-only integrity check. Never rewrite a realtime wallet during a user read.
        _is_verified, verification_details = await verify_wallet_balance(db, current_user.id)
        if verification_details.get("status") == "missing_wallet":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wallet not found for this user.")
        if verification_details.get("status") == "duplicate_wallets":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Multiple wallets found. Manual investigation required.",
            )

        await loan_service.run_loan_maintenance_for_user(
            db=db,
            user_id=current_user.id,
            allow_auto_deduction=False,
        )
        result = await db.execute(select(Wallet).filter(Wallet.user_id == current_user.id))
        wallet = result.scalars().one_or_none()
        if not wallet:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wallet not found for this user.")
        return wallet
    finally:
        await db.close()

@router.get("/transactions/me", response_model=List[dict]) # Generic dict for now or create schema
async def get_my_transactions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    since_id: int = Query(0, ge=0),
    before_id: int | None = Query(None, ge=1),
    limit: int = Query(100, ge=1, le=500),
):
    """
    Retrieve all transactions for the current authenticated user.
    """
    try:
        query = select(Transaction).filter(Transaction.user_id == current_user.id)
        if before_id is not None:
            query = query.filter(Transaction.id < before_id)
        elif since_id > 0:
            query = query.filter(Transaction.id > since_id)
        query = query.order_by(Transaction.id.desc()).limit(limit)
        result = await db.execute(query)
        transactions = result.scalars().all()
        names_by_transaction = await _transaction_counterparty_names(db, transactions, current_user)
        response = []
        for transaction in transactions:
            sender_name, receiver_name, sender_number, receiver_number = names_by_transaction.get(
                int(transaction.id), ("", "", "", "")
            )
            response.append(
                _tx_to_dict(
                    transaction,
                    current_user,
                    sender_name=sender_name,
                    receiver_name=receiver_name,
                    sender_number=sender_number,
                    receiver_number=receiver_number,
                )
            )
        return response
    finally:
        await db.close()


@router.websocket("/transactions/stream")
async def stream_my_transactions(websocket: WebSocket, token: str, since_id: int = 0):
    await websocket.accept()
    user = await _resolve_ws_user(token)
    if not user:
        await websocket.close(code=1008)
        return

    last_seen_id = max(int(since_id or 0), 0)
    heartbeat_seconds = 1.5
    await websocket.send_json(
        {
            "type": "ready",
            "server_time": datetime.now(timezone.utc).isoformat(),
            "last_seen_id": last_seen_id,
        }
    )

    try:
        while True:
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(Transaction)
                    .filter(Transaction.user_id == user.id, Transaction.id > last_seen_id)
                    .order_by(Transaction.id.asc())
                    .limit(200)
                )
                batch = result.scalars().all()

            if batch:
                payload = [_tx_to_dict(t, user) for t in batch]
                last_seen_id = max(t["id"] for t in payload)
                await websocket.send_json(
                    {
                        "type": "transactions",
                        "count": len(payload),
                        "last_seen_id": last_seen_id,
                        "transactions": payload,
                    }
                )
            else:
                await websocket.send_json(
                    {
                        "type": "heartbeat",
                        "server_time": datetime.now(timezone.utc).isoformat(),
                        "last_seen_id": last_seen_id,
                    }
                )

            await asyncio.sleep(heartbeat_seconds)
    except WebSocketDisconnect:
        return
    except Exception:
        try:
            await websocket.close(code=1011)
        except Exception:
            pass


def _parse_wallet_metadata(raw_metadata: str | None) -> dict:
    if not raw_metadata:
        return {}
    try:
        parsed = json.loads(raw_metadata)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


@router.get("/investment/reinvest-toggle", response_model=InvestmentReinvestToggleResponse)
async def get_investment_reinvest_toggle(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        result = await db.execute(select(Wallet).filter(Wallet.user_id == current_user.id))
        wallet = result.scalars().first()
        if not wallet:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wallet not found for this user.")

        metadata = _parse_wallet_metadata(wallet.metadata_json)
        enabled = bool(metadata.get("investment_reinvest_enabled", False))
        return InvestmentReinvestToggleResponse(wallet_id=wallet.id, enabled=enabled)
    finally:
        await db.close()


@router.patch("/investment/reinvest-toggle", response_model=InvestmentReinvestToggleResponse)
async def update_investment_reinvest_toggle(
    request: InvestmentReinvestToggleRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        result = await db.execute(select(Wallet).filter(Wallet.user_id == current_user.id))
        wallet = result.scalars().first()
        if not wallet:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wallet not found for this user.")

        metadata = _parse_wallet_metadata(wallet.metadata_json)
        metadata["investment_reinvest_enabled"] = request.enabled
        wallet.metadata_json = json.dumps(metadata)
        db.add(wallet)
        await db.commit()
        await db.refresh(wallet)
        return InvestmentReinvestToggleResponse(wallet_id=wallet.id, enabled=request.enabled)
    finally:
        await db.close()
