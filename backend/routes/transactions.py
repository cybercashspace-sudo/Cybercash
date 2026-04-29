from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta, timezone
import json
from typing import List

from backend.database import get_db
from backend.models import User, Transaction, Wallet
from backend.dependencies.auth import get_current_user
from backend.schemas.transaction import TransactionResponse
from backend.schemas.transaction_operations import (
    AirtimePurchaseRequest,
    DataPurchaseRequest,
    EscrowCreateRequest,
    EscrowReleaseRequest,
    InvestmentCreateRequest,
    InvestmentPayoutRequest,
    CardSpendRequest,
)
from backend.services.transaction_engine import TransactionEngine, get_transaction_engine
from backend.core.transaction_types import TransactionType
from backend.core.config import settings
from utils.network import normalize_ghana_number


router = APIRouter(prefix="/transactions", tags=["Transactions"])
ESCROW_MIN_DEAL_AMOUNT_GHS = float(getattr(settings, "ESCROW_MIN_DEAL_AMOUNT_GHS", 20.0))
ESCROW_CREATE_FEE_GHS = float(getattr(settings, "ESCROW_CREATE_FEE_GHS", 5.0))
ESCROW_RELEASE_FEE_GHS = float(getattr(settings, "ESCROW_RELEASE_FEE_GHS", 5.0))
INVESTMENT_MIN_AMOUNT_GHS = float(getattr(settings, "INVESTMENT_MIN_AMOUNT_GHS", 10.0))
INVESTMENT_MIN_DAYS = int(getattr(settings, "INVESTMENT_MIN_DAYS", 7))
INVESTMENT_MAX_DAYS = int(getattr(settings, "INVESTMENT_MAX_DAYS", 365))
INVESTMENT_RISK_FREE_ANNUAL_RATE = float(getattr(settings, "INVESTMENT_RISK_FREE_ANNUAL_RATE", 12.0))
INVESTMENT_PROFIT_FEE_RATE = 0.10
INVESTMENT_ALLOWED_DURATIONS_DAYS = (7, 14, 30, 60, 90, 180, 365)


def _security_metadata(payload) -> dict:
    return {
        "pin_verified": payload.pin_verified,
        "biometric_verified": payload.biometric_verified,
        "device_fingerprint": payload.device_fingerprint,
        "ip_address": payload.ip_address,
        "channel": payload.channel,
        "daily_limit": payload.daily_limit,
        "biometric_threshold": payload.biometric_threshold,
        "risk_override": payload.risk_override,
    }


def _parse_metadata(raw_metadata: str | None) -> dict:
    if not raw_metadata:
        return {}
    try:
        parsed = json.loads(raw_metadata)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _normalize_investment_duration_days(duration_days: int | None) -> int:
    days = int(duration_days or 30)
    return days


def _allowed_investment_periods_text() -> str:
    return ", ".join(str(item) for item in INVESTMENT_ALLOWED_DURATIONS_DAYS)


def _compute_investment_profit(amount: float, duration_days: int, annual_rate_pct: float) -> tuple[float, float, float]:
    gross_profit = round(float(amount) * (float(annual_rate_pct) / 100.0) * (float(duration_days) / 365.0), 2)
    profit_fee = round(max(gross_profit, 0.0) * INVESTMENT_PROFIT_FEE_RATE, 2)
    net_profit = round(max(gross_profit - profit_fee, 0.0), 2)
    return gross_profit, profit_fee, net_profit


def _as_aware_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _parse_iso_utc(dt_raw: str | None) -> datetime | None:
    if not dt_raw:
        return None
    try:
        dt = datetime.fromisoformat(str(dt_raw).replace("Z", "+00:00"))
        return _as_aware_utc(dt)
    except Exception:
        return None


@router.post("/airtime", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
async def purchase_airtime(
    request: AirtimePurchaseRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    transaction_engine: TransactionEngine = Depends(get_transaction_engine),
):
    try:
        metadata = _security_metadata(request)
        metadata.update(
            {
                "network": request.network,
                "phone_number": request.phone_number,
                "provider": request.provider,
                "cost_price": request.cost_price,
            }
        )
        return await transaction_engine.process_transaction(
            user_id=current_user.id,
            transaction_type=TransactionType.AIRTIME,
            amount=request.amount,
            metadata=metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    finally:
        await db.close()


@router.post("/data", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
async def purchase_data_bundle(
    request: DataPurchaseRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    transaction_engine: TransactionEngine = Depends(get_transaction_engine),
):
    try:
        normalized_phone = normalize_ghana_number(request.phone_number)
        if not normalized_phone or len(normalized_phone) != 10 or not normalized_phone.isdigit():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Enter a valid 10-digit phone number.")
        metadata = _security_metadata(request)
        metadata.update(
            {
                "network": request.network,
                "phone_number": normalized_phone,
                "bundle_code": request.bundle_code,
                "provider": request.provider,
                "cost_price": request.cost_price,
            }
        )
        return await transaction_engine.process_transaction(
            user_id=current_user.id,
            transaction_type=TransactionType.DATA,
            amount=request.amount,
            metadata=metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    finally:
        await db.close()


@router.post("/escrow/create", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
async def create_escrow(
    request: EscrowCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    transaction_engine: TransactionEngine = Depends(get_transaction_engine),
):
    try:
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
        if request.amount < ESCROW_MIN_DEAL_AMOUNT_GHS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Minimum escrow deal amount is GHS {ESCROW_MIN_DEAL_AMOUNT_GHS:.2f}.",
            )
        if request.amount <= ESCROW_RELEASE_FEE_GHS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Deal amount must exceed GHS {ESCROW_RELEASE_FEE_GHS:.2f} so receiver net remains positive.",
            )

        recipient_result = await db.execute(
            select(User).filter(
                (User.momo_number == recipient_wallet_id) | (User.phone_number == recipient_wallet_id)
            )
        )
        recipient = recipient_result.scalars().first()
        if not recipient or not recipient.is_active or not recipient.is_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Recipient not found. Use an active verified registered number.",
            )
        if recipient.id == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Recipient must be a different user.",
            )

        resolved_recipient_number = normalize_ghana_number(
            str(recipient.momo_number or recipient.phone_number or recipient_wallet_id)
        )

        metadata = _security_metadata(request)
        metadata.update(
            {
                "recipient_id": recipient.id,
                "recipient_wallet_id": resolved_recipient_number,
                "description": request.description,
                "fee": ESCROW_CREATE_FEE_GHS,
                "release_fee": ESCROW_RELEASE_FEE_GHS,
                "receiver_net_amount": max(float(request.amount) - ESCROW_RELEASE_FEE_GHS, 0.0),
                "deal_status": "active",
                "deal_created_at": datetime.utcnow().isoformat(),
                "escrow_fee_currency": "GHS",
            }
        )
        return await transaction_engine.process_transaction(
            user_id=current_user.id,
            transaction_type=TransactionType.ESCROW_CREATE,
            amount=request.amount,
            metadata=metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    finally:
        await db.close()


@router.post("/escrow/release", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
async def release_escrow(
    request: EscrowReleaseRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    transaction_engine: TransactionEngine = Depends(get_transaction_engine),
):
    if not request.escrow_deal_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Escrow deal ID is required. Use /transactions/escrow/{deal_id}/release.",
        )
    return await release_escrow_deal(
        deal_id=request.escrow_deal_id,
        db=db,
        current_user=current_user,
        transaction_engine=transaction_engine,
    )


@router.get("/escrow/deals", response_model=List[dict], status_code=status.HTTP_200_OK)
async def get_escrow_deals(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List escrow deals created by the current user + held funds summary context.
    """
    try:
        tx_result = await db.execute(
            select(Transaction)
            .filter(
                Transaction.user_id == current_user.id,
                Transaction.type == TransactionType.ESCROW_CREATE,
            )
            .order_by(Transaction.timestamp.desc())
        )
        deals = tx_result.scalars().all()

        output = []
        for deal in deals:
            metadata = _parse_metadata(deal.metadata_json)
            deal_status = metadata.get("deal_status", "active")
            output.append(
                {
                    "deal_id": deal.id,
                    "amount": deal.amount,
                    "fee": metadata.get("fee", 0.0),
                    "create_fee": metadata.get("fee", 0.0),
                    "release_fee": metadata.get("release_fee", ESCROW_RELEASE_FEE_GHS),
                    "receiver_net_amount": max(
                        float(deal.amount or 0.0) - float(metadata.get("release_fee", ESCROW_RELEASE_FEE_GHS) or 0.0),
                        0.0,
                    ),
                    "currency": deal.currency,
                    "status": deal_status,
                    "recipient_user_id": metadata.get("recipient_id"),
                    "recipient_wallet_id": metadata.get("recipient_wallet_id"),
                    "description": metadata.get("description") or f"Escrow Deal #{deal.id}",
                    "created_at": deal.timestamp.isoformat() if deal.timestamp else None,
                    "released_at": metadata.get("released_at"),
                    "disputed_at": metadata.get("disputed_at"),
                    "dispute_reason": metadata.get("dispute_reason"),
                    "release_transaction_id": metadata.get("release_transaction_id"),
                }
            )
        return output
    finally:
        await db.close()


@router.post("/escrow/{deal_id}/release", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
async def release_escrow_deal(
    deal_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    transaction_engine: TransactionEngine = Depends(get_transaction_engine),
):
    """
    Release a specific escrow deal by deal id.
    """
    try:
        deal_result = await db.execute(
            select(Transaction).filter(
                Transaction.id == deal_id,
                Transaction.user_id == current_user.id,
                Transaction.type == TransactionType.ESCROW_CREATE,
            )
        )
        deal_tx = deal_result.scalars().first()
        if not deal_tx:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Escrow deal not found.")

        metadata = _parse_metadata(deal_tx.metadata_json)
        deal_status = metadata.get("deal_status", "active")
        if deal_status == "released":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Escrow deal already released.")
        if deal_status == "disputed":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Escrow deal is under dispute.")

        recipient_id = metadata.get("recipient_id")
        if recipient_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Escrow deal recipient is missing.",
            )
        try:
            recipient_id_int = int(recipient_id)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Escrow deal recipient is invalid.",
            )
        if recipient_id_int == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Escrow recipient must be a different user.",
            )

        recipient_result = await db.execute(select(User).filter(User.id == recipient_id_int))
        recipient = recipient_result.scalars().first()
        if not recipient or not recipient.is_active or not recipient.is_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Escrow recipient user is inactive, unverified, or missing.",
            )

        recipient_wallet_id = normalize_ghana_number(
            str(metadata.get("recipient_wallet_id") or recipient.momo_number or recipient.phone_number or "")
        )
        if len(recipient_wallet_id) != 10 or not recipient_wallet_id.isdigit():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Escrow recipient registered number is invalid.",
            )

        release_tx = await transaction_engine.process_transaction(
            user_id=current_user.id,
            transaction_type=TransactionType.ESCROW_RELEASE,
            amount=float(deal_tx.amount),
            metadata={
                "recipient_id": recipient_id_int,
                "recipient_wallet_id": recipient_wallet_id,
                "release_note": f"Released from escrow deal #{deal_id}",
                "escrow_deal_id": deal_id,
                "fee": ESCROW_RELEASE_FEE_GHS,
                "escrow_fee_currency": "GHS",
                "pin_verified": True,
                "biometric_verified": True,
                "channel": "APP",
                "daily_limit": 100000.0,
                "biometric_threshold": 2500.0,
            },
        )

        metadata["deal_status"] = "released"
        metadata["released_at"] = datetime.utcnow().isoformat()
        metadata["release_transaction_id"] = release_tx.id
        metadata["release_fee"] = ESCROW_RELEASE_FEE_GHS
        metadata["recipient_wallet_id"] = recipient_wallet_id
        metadata["receiver_net_amount"] = max(float(deal_tx.amount or 0.0) - ESCROW_RELEASE_FEE_GHS, 0.0)
        deal_tx.metadata_json = json.dumps(metadata)
        db.add(deal_tx)
        await db.commit()
        await db.refresh(release_tx)
        return release_tx
    finally:
        await db.close()


@router.post("/escrow/{deal_id}/dispute", response_model=dict, status_code=status.HTTP_200_OK)
async def dispute_escrow_deal(
    deal_id: int,
    reason: str = "Dispute raised by user",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Flag an escrow deal as disputed.
    """
    try:
        deal_result = await db.execute(
            select(Transaction).filter(
                Transaction.id == deal_id,
                Transaction.user_id == current_user.id,
                Transaction.type == TransactionType.ESCROW_CREATE,
            )
        )
        deal_tx = deal_result.scalars().first()
        if not deal_tx:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Escrow deal not found.")

        metadata = _parse_metadata(deal_tx.metadata_json)
        deal_status = metadata.get("deal_status", "active")
        if deal_status == "released":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot dispute a released deal.")

        metadata["deal_status"] = "disputed"
        metadata["disputed_at"] = datetime.utcnow().isoformat()
        metadata["dispute_reason"] = reason
        deal_tx.metadata_json = json.dumps(metadata)
        db.add(deal_tx)
        await db.commit()
        return {"deal_id": deal_id, "status": "disputed", "reason": reason}
    finally:
        await db.close()


@router.post("/investment/create", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
async def create_investment(
    request: InvestmentCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    transaction_engine: TransactionEngine = Depends(get_transaction_engine),
):
    try:
        if request.amount < INVESTMENT_MIN_AMOUNT_GHS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Minimum investment amount is GHS {INVESTMENT_MIN_AMOUNT_GHS:.2f}.",
            )

        duration_days = _normalize_investment_duration_days(request.duration_days)
        if duration_days < INVESTMENT_MIN_DAYS or duration_days > INVESTMENT_MAX_DAYS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Investment duration must be between {INVESTMENT_MIN_DAYS} and {INVESTMENT_MAX_DAYS} days.",
            )
        if duration_days not in INVESTMENT_ALLOWED_DURATIONS_DAYS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Unsupported investment period selected. "
                    f"Choose one of: {_allowed_investment_periods_text()} days."
                ),
            )

        annual_rate_pct = INVESTMENT_RISK_FREE_ANNUAL_RATE
        gross_profit, profit_fee, net_profit = _compute_investment_profit(
            amount=float(request.amount),
            duration_days=duration_days,
            annual_rate_pct=annual_rate_pct,
        )
        maturity_at = (datetime.utcnow() + timedelta(days=duration_days)).isoformat()

        metadata = _security_metadata(request)
        metadata.update(
            {
                "plan_name": request.plan_name or f"Risk-Free {duration_days}D Plan",
                "duration_days": duration_days,
                "expected_rate": annual_rate_pct,
                "projected_gross_profit": gross_profit,
                "projected_profit_fee": profit_fee,
                "projected_net_profit": net_profit,
                "profit_fee_rate": INVESTMENT_PROFIT_FEE_RATE,
                "investment_status": "active",
                "investment_created_at": datetime.utcnow().isoformat(),
                "maturity_at": maturity_at,
                "investment_currency": "GHS",
            }
        )
        return await transaction_engine.process_transaction(
            user_id=current_user.id,
            transaction_type=TransactionType.INVESTMENT_CREATE,
            amount=request.amount,
            metadata=metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    finally:
        await db.close()


@router.post("/investment/payout", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
async def payout_investment(
    request: InvestmentPayoutRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    transaction_engine: TransactionEngine = Depends(get_transaction_engine),
):
    try:
        if not request.investment_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Investment ID is required to process payout.",
            )

        investment_result = await db.execute(
            select(Transaction).filter(
                Transaction.id == request.investment_id,
                Transaction.user_id == current_user.id,
                Transaction.type == TransactionType.INVESTMENT_CREATE,
            )
        )
        investment_tx = investment_result.scalars().first()
        if not investment_tx:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investment plan not found.")

        investment_metadata = _parse_metadata(investment_tx.metadata_json)
        investment_status = str(investment_metadata.get("investment_status", "active")).strip().lower()
        if investment_status in {"paid_out", "closed"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Investment has already been paid out.")
        if investment_status != "active":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Investment is not active for payout.")

        duration_days = _normalize_investment_duration_days(investment_metadata.get("duration_days"))
        if duration_days < INVESTMENT_MIN_DAYS or duration_days > INVESTMENT_MAX_DAYS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Stored investment duration is invalid ({duration_days} days).",
            )
        if duration_days not in INVESTMENT_ALLOWED_DURATIONS_DAYS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Stored investment period is invalid ({duration_days} days). "
                    f"Allowed periods: {_allowed_investment_periods_text()} days."
                ),
            )

        maturity_at_dt = _parse_iso_utc(investment_metadata.get("maturity_at"))
        if maturity_at_dt is None:
            created_at = _as_aware_utc(investment_tx.timestamp)
            if created_at is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Investment timestamp is missing. Cannot calculate maturity.",
                )
            maturity_at_dt = created_at + timedelta(days=duration_days)
        now_utc = datetime.now(timezone.utc)
        if now_utc < maturity_at_dt:
            days_left = max((maturity_at_dt.date() - now_utc.date()).days, 0)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Investment not yet mature. {days_left} day(s) remaining (matures {maturity_at_dt.date().isoformat()}).",
            )

        principal_amount = float(investment_tx.amount or 0.0)
        annual_rate_pct = float(investment_metadata.get("expected_rate", INVESTMENT_RISK_FREE_ANNUAL_RATE) or INVESTMENT_RISK_FREE_ANNUAL_RATE)
        gross_profit, profit_fee, net_profit = _compute_investment_profit(
            amount=principal_amount,
            duration_days=duration_days,
            annual_rate_pct=annual_rate_pct,
        )

        metadata = _security_metadata(request)
        metadata.update(
            {
                "investment_id": investment_tx.id,
                "plan_name": investment_metadata.get("plan_name") or request.plan_name or f"Risk-Free {duration_days}D Plan",
                "duration_days": duration_days,
                "expected_rate": annual_rate_pct,
                "gross_profit": gross_profit,
                "fee": profit_fee,
                "profit_fee_rate": INVESTMENT_PROFIT_FEE_RATE,
                "gain": net_profit,
                "maturity_at": maturity_at_dt.isoformat(),
                "payout_currency": "GHS",
            }
        )
        payout_tx = await transaction_engine.process_transaction(
            user_id=current_user.id,
            transaction_type=TransactionType.INVESTMENT_PAYOUT,
            amount=principal_amount,
            metadata=metadata,
        )

        investment_metadata["investment_status"] = "paid_out"
        investment_metadata["payout_transaction_id"] = payout_tx.id
        investment_metadata["paid_out_at"] = datetime.utcnow().isoformat()
        investment_metadata["realized_gross_profit"] = gross_profit
        investment_metadata["realized_profit_fee"] = profit_fee
        investment_metadata["realized_net_profit"] = net_profit
        investment_tx.metadata_json = json.dumps(investment_metadata)
        db.add(investment_tx)
        await db.commit()
        await db.refresh(payout_tx)
        return payout_tx
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    finally:
        await db.close()


@router.post("/card/spend", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
async def spend_with_virtual_card(
    request: CardSpendRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    transaction_engine: TransactionEngine = Depends(get_transaction_engine),
):
    try:
        metadata = _security_metadata(request)
        metadata.update(
            {
                "card_id": request.card_id,
                "merchant_name": request.merchant_name,
                "merchant_country": request.merchant_country,
                "fee": request.fee,
                "fx_margin": request.fx_margin,
                "use_card_balance": request.use_card_balance,
                "extra_metadata": request.extra_metadata,
            }
        )
        return await transaction_engine.process_transaction(
            user_id=current_user.id,
            transaction_type=TransactionType.CARD_SPEND,
            amount=request.amount,
            metadata=metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    finally:
        await db.close()
