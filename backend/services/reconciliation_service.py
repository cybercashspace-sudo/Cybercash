# backend/services/reconciliation_service.py
import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import AuditLog, Transaction, User, Wallet
from backend.core.transaction_types import TransactionType, normalize_transaction_type

logger = logging.getLogger(__name__)
MONEY_QUANTIZER = Decimal("0.01")


def _money(value: object) -> Decimal:
    return Decimal(str(value or "0.00")).quantize(MONEY_QUANTIZER)


def _safe_load_metadata(metadata_json: str | None) -> dict[str, Any]:
    if not metadata_json:
        return {}
    try:
        parsed = json.loads(metadata_json)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _metadata_money(metadata: dict[str, Any], *keys: str) -> Decimal:
    for key in keys:
        if key in metadata and metadata.get(key) is not None:
            return _money(metadata.get(key))
    return Decimal("0.00")


def _normalized_transaction_type(raw_type: object) -> str:
    try:
        return normalize_transaction_type(str(raw_type or ""))
    except Exception:
        return str(raw_type or "").strip().upper()


def _debit_delta(amount: Decimal, metadata: dict[str, Any], *fee_keys: str) -> Decimal:
    total_debited = _metadata_money(
        metadata,
        "total_debited",
        "amount_debited",
        "deducted_amount",
        "total_deduction",
    )
    if total_debited > 0:
        return -total_debited
    fees = sum((_metadata_money(metadata, key) for key in fee_keys), Decimal("0.00"))
    return -(amount + fees)


def _wallet_available_delta(transaction: Transaction) -> Decimal:
    amount = _money(transaction.amount)
    if amount < 0:
        return amount

    metadata = _safe_load_metadata(transaction.metadata_json)
    tx_type = _normalized_transaction_type(transaction.type)
    entry_type = str(getattr(transaction, "entry_type", "") or "").strip().lower()

    if tx_type == TransactionType.TRANSFER:
        direction = str(metadata.get("direction", "") or "").strip().lower()
        if direction == "receive":
            return amount
        if direction == "send" or metadata.get("receiver_id") is not None:
            return _debit_delta(amount, metadata, "transfer_fee", "fee")
        if entry_type == "credit":
            return amount
        return _debit_delta(amount, metadata, "transfer_fee", "fee")

    if tx_type in {TransactionType.FUNDING, TransactionType.AGENT_DEPOSIT, TransactionType.LOAN_DISBURSE, TransactionType.CARD_WITHDRAW}:
        return amount

    if tx_type == TransactionType.INVESTMENT_PAYOUT:
        return amount + _metadata_money(metadata, "gain", "net_profit")

    if tx_type == TransactionType.ESCROW_RELEASE:
        recipient_id = metadata.get("recipient_id")
        try:
            is_self_release = recipient_id is None or int(recipient_id) == int(transaction.user_id)
        except (TypeError, ValueError):
            is_self_release = False
        if is_self_release:
            return amount - _metadata_money(metadata, "fee", "release_fee")
        return Decimal("0.00")

    if tx_type in {TransactionType.AGENT_WITHDRAWAL, TransactionType.CARD_LOAD, TransactionType.ESCROW_CREATE}:
        return _debit_delta(amount, metadata, "fee")

    if tx_type == TransactionType.CARD_SPEND:
        return _debit_delta(amount, metadata, "fee", "fx_margin")

    if tx_type in {
        TransactionType.AIRTIME,
        TransactionType.DATA,
        TransactionType.LOAN_REPAY,
        TransactionType.INVESTMENT_CREATE,
        TransactionType.MOBILE_MONEY,
        TransactionType.VIRTUAL_CARD_ISSUANCE_FEE,
        "WITHDRAWAL",
        "ADMIN_BANK_WITHDRAWAL_INITIATE",
    }:
        return -amount

    if entry_type == "debit":
        return -amount
    return amount


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
    )
    if sync_status:
        metadata = {}
        if metadata_json:
            try:
                parsed = json.loads(metadata_json)
                metadata = parsed if isinstance(parsed, dict) else {}
            except Exception:
                metadata = {"raw_metadata": metadata_json}
        metadata["sync_status"] = sync_status
        audit_log.metadata_json = json.dumps(metadata)
    db.add(audit_log)
    await db.flush()
    return audit_log


async def get_wallet_ledger_balance(db: AsyncSession, user_id: int) -> Decimal:
    result = await db.execute(
        select(Transaction).filter(
            Transaction.user_id == user_id,
            Transaction.status == "completed",
        ).order_by(Transaction.id.asc())
    )
    total = sum((_wallet_available_delta(tx) for tx in result.scalars().all()), Decimal("0.00"))
    return _money(total)


async def verify_wallet_balance(
    db: AsyncSession,
    user_id: int,
    *,
    lock_wallet: bool = False,
) -> Tuple[bool, dict]:
    wallet_stmt = select(Wallet).filter(Wallet.user_id == user_id)
    if lock_wallet:
        wallet_stmt = wallet_stmt.with_for_update()
    wallet_result = await db.execute(wallet_stmt)
    wallet = wallet_result.scalars().first()

    if not wallet:
        return False, {
            "user_id": user_id,
            "status": "missing_wallet",
            "error": "Wallet not found. Manual investigation required.",
            "verified_at": datetime.now(timezone.utc).isoformat(),
        }

    ledger_balance = await get_wallet_ledger_balance(db, user_id)
    wallet_balance = _money(wallet.balance)
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
    allow_balance_decrease: bool = False,
) -> Tuple[bool, dict]:
    is_verified, details = await verify_wallet_balance(db, user_id, lock_wallet=True)

    if details.get("status") == "missing_wallet":
        logger.critical("Wallet missing for user_id=%s; refusing automatic recreation", user_id)
        return False, details

    if is_verified:
        await db.execute(
            update(Wallet)
            .where(Wallet.user_id == user_id)
            .values(last_synced_with_ledger=func.now(), last_verified_at=func.now())
        )
        await db.commit()
        return True, details

    tx_count_result = await db.execute(
        select(func.count(Transaction.id)).filter(
            Transaction.user_id == user_id,
            Transaction.status == "completed",
        )
    )
    tx_count = int(tx_count_result.scalar() or 0)

    if tx_count < _min_required_ledger_entries:
        details.update(
            {
                "status": "repair_refused",
                "reason": "ledger_has_no_completed_transactions",
                "completed_transaction_count": tx_count,
            }
        )
        await log_wallet_audit(
            db,
            user_id=user_id,
            action="WALLET_REPAIR_REFUSED",
            before_balance=_money(details.get("wallet_balance")),
            after_balance=_money(details.get("wallet_balance")),
            amount_changed=Decimal("0.00"),
            description=(
                "Wallet repair refused because the completed transaction ledger is empty. "
                "Manual investigation is required before changing the balance."
            ),
            metadata_json=json.dumps(details),
            sync_status="repair_refused",
        )
        await db.commit()
        logger.critical(
            "Wallet repair refused for user_id=%s because completed transaction count is %s",
            user_id,
            tx_count,
        )
        return False, details

    wallet_result = await db.execute(
        select(Wallet).filter(Wallet.user_id == user_id).with_for_update()
    )
    wallet = wallet_result.scalars().first()
    if not wallet:
        return False, {"user_id": user_id, "status": "missing_wallet", "error": "Wallet not found"}

    before_balance = _money(wallet.balance)
    ledger_balance = _money(details.get("ledger_balance"))
    if ledger_balance < before_balance and not allow_balance_decrease:
        details.update(
            {
                "status": "repair_refused",
                "reason": "ledger_balance_would_reduce_wallet_balance",
                "wallet_balance_before": float(before_balance),
                "ledger_balance": float(ledger_balance),
                "completed_transaction_count": tx_count,
                "admin_id": admin_id,
            }
        )
        await log_wallet_audit(
            db,
            user_id=user_id,
            action="WALLET_REPAIR_REFUSED",
            before_balance=before_balance,
            after_balance=before_balance,
            amount_changed=Decimal("0.00"),
            description=(
                "Wallet repair refused because the ledger-derived balance is lower than "
                "the current realtime wallet balance."
            ),
            metadata_json=json.dumps(details),
            sync_status="repair_refused",
        )
        await db.commit()
        logger.warning(
            "Wallet repair refused for user_id=%s because ledger balance %s is below wallet balance %s",
            user_id,
            ledger_balance,
            before_balance,
        )
        return False, details

    wallet.balance = ledger_balance
    wallet.version = int(wallet.version or 0) + 1
    wallet.last_synced_with_ledger = datetime.now(timezone.utc)
    wallet.last_verified_at = datetime.now(timezone.utc)
    db.add(wallet)
    await db.flush()

    details.update(
        {
            "wallet_balance_before": float(before_balance),
            "wallet_balance_after": float(ledger_balance),
            "completed_transaction_count": tx_count,
            "status": "repaired",
            "admin_id": admin_id,
        }
    )
    await log_wallet_audit(
        db,
        user_id=user_id,
        action="WALLET_BALANCE_REPAIRED",
        before_balance=before_balance,
        after_balance=ledger_balance,
        amount_changed=ledger_balance - before_balance,
        description="Wallet balance repaired from completed transaction ledger.",
        metadata_json=json.dumps(details),
        sync_status="repaired",
    )
    await db.commit()
    return True, details


async def get_audit_logs_for_user(
    db: AsyncSession,
    user_id: int,
    limit: int = 100,
) -> List[AuditLog]:
    result = await db.execute(
        select(AuditLog)
        .filter(AuditLog.user_id == user_id, AuditLog.resource_type == "wallet")
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def find_wallet_integrity_issues(db: AsyncSession) -> List[Dict]:
    duplicate_rows = await db.execute(
        select(Wallet.user_id, func.count(Wallet.id))
        .group_by(Wallet.user_id)
        .having(func.count(Wallet.id) != 1)
    )
    issues = [
        {"user_id": int(user_id), "wallet_count": int(wallet_count)}
        for user_id, wallet_count in duplicate_rows.all()
    ]

    missing_rows = await db.execute(
        select(User.id)
        .outerjoin(Wallet, Wallet.user_id == User.id)
        .group_by(User.id)
        .having(func.count(Wallet.id) == 0)
    )
    issues.extend(
        {"user_id": int(user_id), "wallet_count": 0}
        for user_id in missing_rows.scalars().all()
    )
    return issues


async def reconcile_all_wallets(
    db: AsyncSession,
    *,
    freeze_on_mismatch: bool = False,
) -> Dict[str, int]:
    wallet_rows = await db.execute(select(Wallet).order_by(Wallet.user_id.asc()))
    wallets = list(wallet_rows.scalars().all())

    report = {
        "total_users": len(wallets),
        "verified_count": 0,
        "mismatch_count": 0,
        "locked_count": 0,
        "missing_wallet_count": 0,
    }

    for wallet in wallets:
        is_verified, details = await verify_wallet_balance(db, int(wallet.user_id))
        if details.get("status") == "missing_wallet":
            report["missing_wallet_count"] += 1
            continue

        if is_verified:
            report["verified_count"] += 1
            wallet.last_verified_at = datetime.now(timezone.utc)
            db.add(wallet)
            continue

        report["mismatch_count"] += 1
        if freeze_on_mismatch and not wallet.is_frozen:
            wallet.is_frozen = True
            report["locked_count"] += 1
            db.add(wallet)

        await log_wallet_audit(
            db,
            user_id=int(wallet.user_id),
            action="WALLET_RECONCILIATION_MISMATCH",
            before_balance=_money(details.get("wallet_balance")),
            after_balance=_money(details.get("ledger_balance")),
            amount_changed=_money(details.get("ledger_balance")) - _money(details.get("wallet_balance")),
            description="Wallet balance mismatch detected during scheduled reconciliation.",
            metadata_json=json.dumps(details),
            sync_status="mismatch",
        )

    await db.commit()
    return report
