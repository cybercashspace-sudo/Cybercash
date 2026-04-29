
import asyncio
from datetime import datetime, timezone, timedelta
import json
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.database import AsyncSessionLocal, get_db
from backend.models import Agent, User, Wallet, Transaction
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
from backend.core.transaction_types import TransactionType

router = APIRouter(prefix="/wallet", tags=["Wallet"])
ALLOWED_SOURCE_BALANCES = {
    "balance": "Main Balance",
    "escrow_balance": "Escrow Balance",
    "loan_balance": "Loan Balance",
    "investment_balance": "Investment Balance",
}
MIN_TRANSFER_AMOUNT_GHS = 1.0
WITHDRAW_TO_AGENT_FEE_RATE = 0.01
P2P_TRANSFER_FEE_RATE = 0.005
P2P_DAILY_FREE_LIMIT_GHS = 100.0


def _safe_load_metadata(metadata_json: str | None) -> dict:
    if not metadata_json:
        return {}
    try:
        value = json.loads(metadata_json)
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


async def _resolve_p2p_total_sent_today(db: AsyncSession, *, user_id: int) -> float:
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

    total_sent = 0.0
    for tx in transactions:
        metadata = _safe_load_metadata(tx.metadata_json)
        if str(metadata.get("direction", "")).lower() != "send":
            continue
        if str(metadata.get("transfer_kind", "")).lower() != "wallet_transfer":
            continue

        transferred_amount = metadata.get("transferred_amount")
        if transferred_amount is None:
            transferred_amount = abs(float(tx.amount or 0.0))
            fee = float(metadata.get("transfer_fee", 0.0) or 0.0)
            transferred_amount = max(0.0, transferred_amount - fee)
        total_sent += float(transferred_amount or 0.0)

    return round(total_sent, 2)


def _tx_to_dict(t: Transaction) -> dict:
    timestamp = t.timestamp
    if timestamp and timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return {
        "id": t.id,
        "type": t.type,
        "amount": t.amount,
        "currency": t.currency,
        "status": t.status,
        "timestamp": timestamp.isoformat() if timestamp else datetime.now(timezone.utc).isoformat(),
        "metadata_json": t.metadata_json,
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
        free_remaining = max(0.0, round(P2P_DAILY_FREE_LIMIT_GHS - total_sent_today, 2))
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
    ledger_service: LedgerService = Depends(get_ledger_service)
):
    try:
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

        requested_amount = round(float(request.amount), 2)
        fee_rate = WITHDRAW_TO_AGENT_FEE_RATE if is_agent_withdraw else P2P_TRANSFER_FEE_RATE

        p2p_total_sent_today_before = 0.0
        p2p_free_remaining_before = 0.0
        p2p_fee_free_amount = 0.0
        p2p_feeable_amount = requested_amount

        if not is_agent_withdraw:
            p2p_total_sent_today_before = await _resolve_p2p_total_sent_today(db, user_id=current_user.id)
            p2p_free_remaining_before = max(0.0, round(P2P_DAILY_FREE_LIMIT_GHS - p2p_total_sent_today_before, 2))
            p2p_fee_free_amount = min(requested_amount, p2p_free_remaining_before)
            p2p_feeable_amount = max(0.0, round(requested_amount - p2p_free_remaining_before, 2))

        transfer_fee = round(p2p_feeable_amount * fee_rate, 2)
        total_debited = round(requested_amount + transfer_fee, 2)

        # Sender's wallet
        result = await db.execute(select(Wallet).filter(Wallet.user_id == current_user.id))
        sender_wallet = result.scalars().first()
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

        sender_source_balance = float(getattr(sender_wallet, source_balance_key, 0.0) or 0.0)
        required_amount = total_debited
        if sender_source_balance < required_amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient balance in {ALLOWED_SOURCE_BALANCES[source_balance_key]}.",
            )

        recipient_wallet_id = normalize_ghana_number(request.recipient_wallet_id or "").strip()

        if not recipient_wallet_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="recipient_wallet_id (registered number) is required.",
            )
        if len(recipient_wallet_id) != 10 or not recipient_wallet_id.isdigit():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="recipient_wallet_id must be a valid 10-digit registered number.",
            )

        # Recipient resolution strictly by wallet ID (registered number).
        result = await db.execute(
            select(User).filter(
                (User.momo_number == recipient_wallet_id) | (User.phone_number == recipient_wallet_id)
            )
        )
        recipient_user = result.scalars().first()

        if not recipient_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipient user not found for this wallet ID.")
        
        if recipient_user.id == current_user.id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot transfer funds to yourself.")

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

        result = await db.execute(select(Wallet).filter(Wallet.user_id == recipient_user.id))
        recipient_wallet = result.scalars().first()
        if not recipient_wallet:
            # Create a wallet for the recipient if they don't have one
            recipient_wallet = Wallet(user_id=recipient_user.id, currency=request.currency, balance=0.0)
            db.add(recipient_wallet)
            await db.flush() # Flush to get recipient_wallet.id
        
        if recipient_wallet.is_frozen:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Recipient's wallet is currently frozen by administration."
            )

        # Atomic transfer operation: wallet updates + transaction logs + ledger in one DB commit.
        setattr(sender_wallet, source_balance_key, sender_source_balance - required_amount)
        recipient_wallet.balance += requested_amount

        sender_transaction = Transaction(
            user_id=current_user.id,
            wallet_id=sender_wallet.id,
            type=TransactionType.TRANSFER,
            amount=-required_amount,
            currency=request.currency,
            status="completed",
            metadata_json=json.dumps(
                {
                    "direction": "send",
                    "recipient_wallet_id": recipient_user.momo_number or recipient_user.phone_number,
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
                }
            ),
        )
        db.add(sender_transaction)
        await db.flush()

        recipient_transaction = Transaction(
            user_id=recipient_user.id,
            wallet_id=recipient_wallet.id,
            type=TransactionType.TRANSFER,
            amount=requested_amount,
            currency=request.currency,
            status="completed",
            metadata_json=json.dumps(
                {
                    "direction": "receive",
                    "sender_wallet_id": current_user.momo_number or current_user.phone_number,
                    "source_balance": source_balance_key,
                    "transfer_kind": "withdraw_to_agent" if is_agent_withdraw else "wallet_transfer",
                    "transferred_amount": requested_amount,
                    "transfer_fee": transfer_fee,
                    "transfer_fee_rate": fee_rate,
                }
            ),
        )
        db.add(recipient_transaction)
        await db.flush()

        sender_identifier = current_user.momo_number or current_user.phone_number or f"user:{current_user.id}"
        recipient_identifier = recipient_user.momo_number or recipient_user.phone_number or f"user:{recipient_user.id}"

        ledger_entries_data = [
            {"account_name": "Customer Wallets (Liability)", "debit": required_amount, "credit": 0.0},
            {"account_name": "Customer Wallets (Liability)", "debit": 0.0, "credit": requested_amount},
        ]
        if transfer_fee > 0:
            ledger_entries_data.append(
                {"account_name": "Revenue - Transaction Fees", "debit": 0.0, "credit": transfer_fee}
            )

        await ledger_service.create_journal_entry(
            description=f"Funds transfer from {sender_identifier} to {recipient_identifier}",
            ledger_entries_data=ledger_entries_data,
            transaction=sender_transaction,
            auto_commit=False,
        )

        await db.commit()
        await loan_service.run_loan_maintenance_for_user(
            db=db,
            user_id=recipient_user.id,
            allow_auto_deduction=True,
        )
        await db.refresh(sender_wallet) # Refresh sender wallet to return updated balance
        transfer_reference = f"TRX-{int(sender_transaction.id)}"
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
        await loan_service.run_loan_maintenance_for_user(
            db=db,
            user_id=current_user.id,
            allow_auto_deduction=False,
        )
        result = await db.execute(select(Wallet).filter(Wallet.user_id == current_user.id))
        wallet = result.scalars().first()
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
    limit: int = Query(100, ge=1, le=500),
):
    """
    Retrieve all transactions for the current authenticated user.
    """
    try:
        query = select(Transaction).filter(Transaction.user_id == current_user.id)
        if since_id > 0:
            query = query.filter(Transaction.id > since_id)
        query = query.order_by(Transaction.timestamp.desc()).limit(limit)
        result = await db.execute(query)
        transactions = result.scalars().all()
        return [_tx_to_dict(t) for t in transactions]
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
                payload = [_tx_to_dict(t) for t in batch]
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
