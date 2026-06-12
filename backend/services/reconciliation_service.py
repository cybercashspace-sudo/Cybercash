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
    admin_id: Optional[int] = None
) -> Tuple[bool, dict]:
    """
    Recalculates balance from ledger and updates the wallet.
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

    ledger_balance = Decimal(str(details.get("ledger_balance", "0.00")))
    wallet_balance = Decimal(str(details.get("wallet_balance", "0.00")))
    difference = ledger_balance - wallet_balance

    res = await db.execute(
        select(Wallet).filter(Wallet.user_id == user_id).with_for_update()
    )
    wallet = res.scalars().first()
    
    if not wallet:
        return False, {"error": "Wallet not found"}

    wallet.balance = ledger_balance
    wallet.version += 1
    wallet.last_synced_with_ledger = func.now()
    wallet.last_verified_at = func.now()
    if admin_id and wallet.is_frozen:
        wallet.is_frozen = False
    
    action = "MANUAL_BALANCE_REPAIR" if admin_id else "AUTO_BALANCE_REPAIR"
    
    await log_wallet_audit(
        db,
        user_id=user_id,
        action=action,
        before_balance=details["wallet_balance"],
        after_balance=details["ledger_balance"],
        amount_changed=difference,
        description=f"Balance repaired from ledger. Difference: {difference}",
        sync_status="repaired",
        metadata_json=json.dumps(details)
    )
    
    await db.commit()
    await db.refresh(wallet)
    
    details["status"] = "repaired"
    details["wallet_balance"] = float(ledger_balance)
    details["difference"] = 0.0
    return True, details


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
                # Update last verified timestamp for successful audits
                wallet_res = await db.execute(select(Wallet).filter(Wallet.user_id == user.id))
                wallet_obj = wallet_res.scalars().first()
                if wallet_obj:
                    wallet_obj.last_verified_at = func.now()
                    wallet_obj.last_synced_with_ledger = func.now()
            else:
                mismatch_count += 1
                difference = Decimal(str(details.get("difference", "0.00")))
                
                # Log mismatch to audit
                await log_wallet_audit(
                    db,
                    user_id=user.id,
                    action="WALLET_RECONCILIATION_MISMATCH",
                    description=f"Balance mismatch detected at version {details['version']}: wallet={details['wallet_balance']}, ledger={details['ledger_balance']}, diff={difference}",
                    before_balance=details["wallet_balance"],
                    after_balance=details["ledger_balance"],
                    amount_changed=difference,
                    metadata_json=str(details),
                    sync_status="mismatch",
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
