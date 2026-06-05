# backend/services/reconciliation_service.py
import logging
from datetime import datetime, timezone
from typing import Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from backend.models import Wallet, Transaction, User, AuditLog
from backend.core.transaction_types import TransactionType

logger = logging.getLogger(__name__)


async def log_wallet_audit(
    db: AsyncSession,
    *,
    user_id: int,
    action: str,
    transaction_id: Optional[int] = None,
    before_balance: Optional[float] = None,
    after_balance: Optional[float] = None,
    amount_changed: Optional[float] = None,
    ip_address: Optional[str] = None,
    device_fingerprint: Optional[str] = None,
    description: Optional[str] = None,
    metadata_json: Optional[str] = None,
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
        before_balance=before_balance,
        after_balance=after_balance,
        amount_changed=amount_changed,
        ip_address=ip_address,
        device_fingerprint=device_fingerprint,
        description=description,
        metadata_json=metadata_json,
    )
    db.add(audit_log)
    await db.flush()
    return audit_log


async def get_wallet_ledger_balance(
    db: AsyncSession,
    user_id: int,
) -> float:
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
    total = result.scalar() or 0.0
    return round(float(total), 2)


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
    wallet_balance = round(float(wallet.balance or 0.0), 2)
    is_verified = abs(wallet_balance - ledger_balance) < 0.01  # Allow for floating point rounding
    
    return is_verified, {
        "wallet_id": wallet.id,
        "user_id": user_id,
        "wallet_balance": wallet_balance,
        "ledger_balance": ledger_balance,
        "difference": round(wallet_balance - ledger_balance, 2),
        "status": "verified" if is_verified else "mismatch",
        "verified_at": datetime.now(timezone.utc).isoformat(),
    }


async def reconcile_all_wallets(
    db: AsyncSession,
) -> dict:
    """
    Daily reconciliation job: verify all wallets against their transaction ledgers.
    Logs mismatches and locks affected wallets.
    
    Returns:
        Report with total_users, verified_count, mismatch_count, locked_count
    """
    logger.info("Starting daily wallet reconciliation...")
    
    # Get all active users
    user_result = await db.execute(
        select(User).filter(User.is_active == True, User.is_deleted == False)
    )
    users = user_result.scalars().all()
    
    verified_count = 0
    mismatch_count = 0
    locked_count = 0
    mismatches = []
    
    for user in users:
        try:
            is_verified, details = await verify_wallet_balance(db, user.id)
            
            if is_verified:
                verified_count += 1
            else:
                mismatch_count += 1
                difference = details.get("difference", 0.0)
                
                # Log mismatch to audit
                await log_wallet_audit(
                    db,
                    user_id=user.id,
                    action="WALLET_RECONCILIATION_MISMATCH",
                    description=f"Balance mismatch detected: wallet={details['wallet_balance']}, ledger={details['ledger_balance']}, diff={difference}",
                    before_balance=details["wallet_balance"],
                    after_balance=details["ledger_balance"],
                    amount_changed=difference,
                    metadata_json=str(details),
                )
                
                # Lock the wallet to prevent further transactions
                wallet_result = await db.execute(
                    select(Wallet).filter(Wallet.user_id == user.id)
                )
                wallet = wallet_result.scalars().first()
                if wallet and not wallet.is_frozen:
                    wallet.is_frozen = True
                    db.add(wallet)
                    locked_count += 1
                    logger.warning(
                        f"Wallet locked for user {user.id}: balance mismatch ${difference}"
                    )
                
                mismatches.append(details)
        
        except Exception as e:
            logger.error(f"Error reconciling wallet for user {user.id}: {str(e)}")
            continue
    
    await db.commit()
    
    report = {
        "reconciliation_timestamp": datetime.now(timezone.utc).isoformat(),
        "total_users": len(users),
        "verified_count": verified_count,
        "mismatch_count": mismatch_count,
        "locked_count": locked_count,
        "mismatches": mismatches,
    }
    
    logger.info(
        f"Reconciliation complete: {verified_count} verified, {mismatch_count} mismatches, {locked_count} locked"
    )
    
    return report


async def get_audit_logs_for_user(
    db: AsyncSession,
    user_id: int,
    limit: int = 100,
) -> list:
    """
    Retrieve audit logs for a specific user (for support/compliance).
    """
    result = await db.execute(
        select(AuditLog)
        .filter(AuditLog.user_id == user_id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()
