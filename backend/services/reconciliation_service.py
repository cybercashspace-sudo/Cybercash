# backend/services/reconciliation_service.py
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Tuple, List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from backend.models import Wallet, Transaction, User, AuditLog
from backend.core.transaction_types import TransactionType
import json

logger = logging.getLogger(__name__)


async def log_wallet_audit(
    db: AsyncSession,
    *,
    user_id: int,
    action: str,
    transaction_id: Optional[int] = None,
    before_balance: Optional[Decimal] = None,
    after_balance: Optional[Decimal] = None,
    amount_changed: Optional[Decimal] = None,
    ip_address: Optional[str] = None,
    device_fingerprint: Optional[str] = None,
    description: Optional[str] = None,
    metadata_json: Optional[str] = None,
    sync_status: Optional[str] = None,
) -> AuditLog:
    """
    Log a wallet action to the audit trail.
    Used for tracking all balance changes and transactions.
    """
    audit_log = AuditLog(
        user_id=user_id,
        action=action,
        transaction_id=transaction_id,
        resource_type="wallet",
        before_balance=float(before_balance) if before_balance is not None else None,
        after_balance=float(after_balance) if after_balance is not None else None,
        amount_changed=float(amount_changed) if amount_changed is not None else None,
        ip_address=ip_address,
        device_fingerprint=device_fingerprint,
        description=description,
        metadata_json=metadata_json,
        sync_status=sync_status,
    )
    db.add(audit_log)
    await db.flush()
    return audit_log


async def get_wallet_ledger_balance(
    db: AsyncSession,
    user_id: int,
) -> Decimal:
    """
    Calculate the wallet balance directly from the transaction ledger.
    This is the SOURCE OF TRUTH for balance verification.
    
    Returns the sum of all transaction amounts for the user.
    """
    result = await db.execute(
        select(func.sum(Transaction.amount)).filter(
            Transaction.user_id == user_id,
            Transaction.status == "completed",
        )
    )
    total = result.scalar() or Decimal("0.00")
    return Decimal(str(total)).quantize(Decimal("0.01"))


async def verify_wallet_balance(
    db: AsyncSession,
    user_id: int,
) -> Tuple[bool, dict]:
    """
    Verify that a wallet's balance matches the transaction ledger.
    
    Returns:
        (is_verified: bool, details: dict)
    """
    # Get wallet
    wallet_result = await db.execute(
        select(Wallet).filter(Wallet.user_id == user_id).with_for_update()
    )
    wallet = wallet_result.scalars().first()
    
    if not wallet:
        return False, {"error": "Wallet not found"}
    
    # Calculate ledger balance from transactions
    ledger_balance = await get_wallet_ledger_balance(db, user_id)
    
    # Compare
    wallet_balance = Decimal(str(wallet.balance or "0.00")).quantize(Decimal("0.01"))
    is_verified = wallet_balance == ledger_balance
    
    return is_verified, {
        "wallet_id": wallet.id,
        "user_id": user_id,
        "version": wallet.version,
        "wallet_balance": float(wallet_balance),
        "ledger_balance": float(ledger_balance),
        "difference": float(wallet_balance - ledger_balance),
        "status": "verified" if is_verified else "mismatch",
        "verified_at": datetime.now(timezone.utc).isoformat(),
    }


async def repair_wallet_balance(
    db: AsyncSession,
    user_id: int,
    admin_id: Optional[int] = None,
    *,
    _min_required_ledger_entries: int = 1,
) -> Tuple[bool, dict]:
    """
    Recalculates balance from ledger and updates the wallet.
    
    SAFETY GUARD: Will NOT repair balance to zero if the user has fewer than
    _min_required_ledger_entries completed transactions in the ledger. This
    prevents the wallet being wiped to zero after long inactivity where the
    session/connection may return incomplete data.
    
    Logs the action in AuditLog with sync_status.
    """
    is_verified, details = await verify_wallet_balance(db, user_id)
    
    if is_verified:
        await db.execute(
            update(Wallet)
            .where(Wallet.user_id == user_id)
            .values(last_synced_with_ledger=func.now(), last_verified_at=func.now())
        )
        await db.commit()
        return True, details

    # ===== SAFETY CHECK: count completed transactions before repairing =====
    tx_count_result = await db.execute(
        select(func.count(Transaction.id)).filter(
            Transaction.user_id == user_id,
            Transaction.status == "completed",
        )
    )
    tx_count = tx_count_result.scalar() or 0

    if tx_count < _min_required_ledger_entries:
        # Refuse to repair – the ledger likely has stale
