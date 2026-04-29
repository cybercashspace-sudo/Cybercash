import json
import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.core.transaction_types import TransactionType
from backend.database import get_db
from backend.dependencies.auth import get_current_user
from backend.models import AirtimeCashSale, AirtimeCashSmsLog, Transaction, User, Wallet
from backend.schemas.airtime import (
    AirtimeCashConfirmRequest,
    AirtimeCashQuoteRequest,
    AirtimeCashQuoteResponse,
    AirtimeCashSaleResponse,
    AirtimeCashSmsWebhook,
    AirtimePurchaseRequest,
)
from backend.schemas.transaction import TransactionResponse
from backend.services.momo import MomoService
from backend.services.notification import NotificationService
from utils.network import normalize_ghana_number


router = APIRouter(prefix="/api/airtime", tags=["Airtime"])
momo_service = MomoService()
notification_service = NotificationService()

SUPPORTED_NETWORKS = {"MTN", "VODAFONE", "AIRTELTIGO"}
AIRTIME_CASH_NETWORKS = {"MTN", "TELECEL", "AIRTELTIGO"}
AIRTIME_CASH_PAYOUT_RATE = float(getattr(settings, "AIRTIME_CASH_PAYOUT_RATE", 0.80))
AIRTIME_CASH_MIN_AMOUNT = float(getattr(settings, "AIRTIME_CASH_MIN_AMOUNT", 1.0))
AIRTIME_CASH_MAX_AMOUNT = float(getattr(settings, "AIRTIME_CASH_MAX_AMOUNT", 1000.0))
AIRTIME_CASH_MANUAL_REVIEW_THRESHOLD = float(
    getattr(settings, "AIRTIME_CASH_MANUAL_REVIEW_THRESHOLD", 200.0)
)
AIRTIME_CASH_MERCHANT_NUMBERS = {
    "MTN": getattr(settings, "AIRTIME_CASH_MERCHANT_MTN", "0559000000"),
    "TELECEL": getattr(settings, "AIRTIME_CASH_MERCHANT_TELECEL", "0209000000"),
    "AIRTELTIGO": getattr(settings, "AIRTIME_CASH_MERCHANT_AIRTELTIGO", "0279000000"),
}
AIRTIME_CASH_MERCHANT_DEFAULT = getattr(settings, "AIRTIME_CASH_MERCHANT_DEFAULT", "0559000000")


def _normalize_cash_network(network: str) -> str:
    raw = str(network or "").strip().upper()
    if raw in {"VODAFONE", "TELECEL"}:
        return "TELECEL"
    if raw in {"AIRTEL", "TIGO", "AIRTELTIGO", "AIRTEL TIGO"}:
        return "AIRTELTIGO"
    if raw == "MTN":
        return "MTN"
    return raw


def _resolve_cash_merchant(network: str) -> str:
    normalized = _normalize_cash_network(network)
    return AIRTIME_CASH_MERCHANT_NUMBERS.get(normalized, AIRTIME_CASH_MERCHANT_DEFAULT)


def _parse_airtime_sms(message: str) -> tuple[str | None, float | None]:
    text = str(message or "").strip()
    if not text:
        return None, None

    amount_match = re.search(r"(?:GHS|GHc)\s*([0-9]+(?:\.[0-9]{1,2})?)", text, re.IGNORECASE)
    sender_match = re.search(r"from\s+(\+?\d{9,15})", text, re.IGNORECASE)

    amount = float(amount_match.group(1)) if amount_match else None
    sender = normalize_ghana_number(sender_match.group(1)) if sender_match else None
    return sender, amount


def _parse_metadata_json(raw_metadata: str | None) -> dict:
    if not raw_metadata:
        return {}
    try:
        parsed = json.loads(raw_metadata)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


async def _trigger_airtime_cash_payout(
    sale: AirtimeCashSale,
    metadata: dict,
    db: AsyncSession,
) -> AirtimeCashSale:
    callback_url = str(getattr(settings, "AIRTIME_CASH_MOMO_CALLBACK_URL", "") or "")
    momo_response = await momo_service.initiate_withdrawal(
        phone_number=sale.phone,
        amount=float(sale.payout_amount),
        currency=sale.currency or "GHS",
        user_id=sale.user_id,
        callback_url=callback_url,
    )
    metadata["payout_response"] = momo_response
    sale.payout_provider = "momo"
    sale.provider_reference = momo_response.get("processor_transaction_id")
    status_value = str(momo_response.get("status", "") or "").strip().lower()

    now = datetime.now(timezone.utc)
    if status_value in {"successful", "success", "completed"}:
        sale.status = "paid"
        sale.paid_at = now
    elif status_value in {"failed", "error"}:
        sale.status = "failed"
    else:
        sale.status = "payout_pending"

    sale.metadata_json = json.dumps(metadata)
    db.add(sale)
    await db.flush()
    return sale


@router.post("/purchase", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
async def purchase_airtime(
    request: AirtimePurchaseRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        network = request.network.upper()
        if network not in SUPPORTED_NETWORKS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported network. Use MTN, VODAFONE, or AIRTELTIGO.",
            )

        result = await db.execute(select(Wallet).filter(Wallet.user_id == current_user.id))
        wallet = result.scalars().first()
        if not wallet:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wallet not found.")
        if wallet.balance < request.amount:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Insufficient wallet balance.")

        # Deduct wallet before provider call.
        wallet.balance -= request.amount
        transaction = Transaction(
            user_id=current_user.id,
            wallet_id=wallet.id,
            type=TransactionType.AIRTIME,
            amount=request.amount,
            currency=wallet.currency or "GHS",
            status="pending",
            metadata_json=json.dumps(
                {
                    "network": network,
                    "phone": request.phone,
                }
            ),
        )
        db.add(wallet)
        db.add(transaction)
        await db.flush()

        provider_response = await momo_service.initiate_airtime_payment(
            phone_number=request.phone,
            amount=request.amount,
            currency=transaction.currency,
            network_provider=network,
            user_id=current_user.id,
        )
        provider_status = (provider_response.get("status") or "").lower()
        provider_ref = provider_response.get("processor_transaction_id") or f"MOMO_{uuid.uuid4().hex}"

        transaction.provider = "momo"
        transaction.provider_reference = provider_ref
        transaction.metadata_json = json.dumps(
            {
                "network": network,
                "phone": request.phone,
                "provider_response": provider_response,
            }
        )

        if provider_status in {"successful", "success", "completed"}:
            transaction.status = "completed"
            await db.commit()
            await db.refresh(transaction)
            normalized_phone = normalize_ghana_number(request.phone)
            await notification_service.send_sms(
                normalized_phone or request.phone,
                f"CyberCash: Airtime purchase successful. {transaction.currency} {request.amount:.2f} on {network}.",
            )
            return transaction

        # Provider failed: refund wallet and mark failed.
        wallet.balance += request.amount
        db.add(wallet)
        transaction.status = "failed"
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=provider_response.get("message", "Airtime purchase failed at provider."),
        )
    finally:
        await db.close()


@router.post("/cash/quote", response_model=AirtimeCashQuoteResponse, status_code=status.HTTP_201_CREATED)
async def create_airtime_cash_quote(
    request: AirtimeCashQuoteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        phone = normalize_ghana_number(request.phone)
        if not phone or len(phone) != 10 or not phone.isdigit():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Enter a valid 10-digit phone number.")

        network = _normalize_cash_network(request.network)
        if network not in AIRTIME_CASH_NETWORKS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported network. Use MTN, Telecel, or AirtelTigo.",
            )

        amount = float(request.amount)
        if amount < AIRTIME_CASH_MIN_AMOUNT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Minimum airtime amount is GHS {AIRTIME_CASH_MIN_AMOUNT:.2f}.",
            )
        if amount > AIRTIME_CASH_MAX_AMOUNT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Maximum airtime amount is GHS {AIRTIME_CASH_MAX_AMOUNT:.2f}.",
            )

        payout_rate = max(0.5, min(float(AIRTIME_CASH_PAYOUT_RATE), 0.95))
        payout_amount = round(amount * payout_rate, 2)
        fee_amount = round(amount - payout_amount, 2)
        merchant_number = _resolve_cash_merchant(network)

        requires_review = amount >= AIRTIME_CASH_MANUAL_REVIEW_THRESHOLD
        status_value = "manual_review" if requires_review else "pending"
        metadata = {
            "requires_manual_review": requires_review,
            "fee_amount": fee_amount,
            "payout_rate": payout_rate,
        }

        sale = AirtimeCashSale(
            user_id=current_user.id,
            phone=phone,
            network=network,
            amount=amount,
            payout_amount=payout_amount,
            payout_rate=payout_rate,
            currency=request.currency or "GHS",
            status=status_value,
            merchant_number=merchant_number,
            metadata_json=json.dumps(metadata),
        )
        db.add(sale)
        await db.commit()
        await db.refresh(sale)

        instructions = (
            f"Send GHS {amount:,.2f} airtime from {phone} to {merchant_number}. "
            f"We will verify receipt and pay out about GHS {payout_amount:,.2f} to your MoMo."
        )
        if requires_review:
            instructions = f"{instructions} Large amounts require manual review before payout."

        return AirtimeCashQuoteResponse(
            sale_id=sale.id,
            merchant_number=merchant_number,
            payout_rate=payout_rate,
            payout_amount=payout_amount,
            fee_amount=fee_amount,
            status=sale.status,
            instructions=instructions,
        )
    finally:
        await db.close()


@router.post("/cash/confirm", response_model=AirtimeCashSaleResponse, status_code=status.HTTP_200_OK)
async def confirm_airtime_cash_transfer(
    request: AirtimeCashConfirmRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        result = await db.execute(
            select(AirtimeCashSale).filter(
                AirtimeCashSale.id == request.sale_id,
                AirtimeCashSale.user_id == current_user.id,
            )
        )
        sale = result.scalars().first()
        if not sale:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Airtime sale not found.")

        if sale.status in {"paid", "payout_pending"}:
            return sale

        metadata = _parse_metadata_json(sale.metadata_json)
        metadata["confirmed_at"] = datetime.now(timezone.utc).isoformat()
        requires_review = bool(metadata.get("requires_manual_review")) or sale.amount >= AIRTIME_CASH_MANUAL_REVIEW_THRESHOLD

        sale.status = "manual_review" if requires_review else "submitted"
        sale.metadata_json = json.dumps(metadata)
        db.add(sale)
        await db.commit()
        await db.refresh(sale)
        note = (
            f"CyberCash: Airtime transfer noted for {sale.currency} {sale.amount:.2f}. "
            "Verification is in progress."
        )
        if requires_review:
            note = (
                f"CyberCash: Airtime transfer noted for {sale.currency} {sale.amount:.2f}. "
                "Manual review is required before payout."
            )
        normalized_sale_phone = normalize_ghana_number(sale.phone)
        await notification_service.send_sms(normalized_sale_phone or sale.phone, note)
        return sale
    finally:
        await db.close()


@router.post("/cash/sms", status_code=status.HTTP_202_ACCEPTED)
async def receive_airtime_cash_sms(
    payload: AirtimeCashSmsWebhook,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    try:
        expected_token = str(getattr(settings, "AIRTIME_CASH_SMS_WEBHOOK_TOKEN", "") or "").strip()
        if expected_token:
            provided = request.headers.get("X-Airtime-Webhook-Token") or request.query_params.get("token")
            if not provided or provided != expected_token:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid SMS webhook token.")

        parsed_sender, parsed_amount = _parse_airtime_sms(payload.message)
        if payload.sender:
            parsed_sender = normalize_ghana_number(payload.sender) or parsed_sender

        matched_sale = None
        if parsed_sender and parsed_amount:
            amount_min = float(parsed_amount) - 0.01
            amount_max = float(parsed_amount) + 0.01
            result = await db.execute(
                select(AirtimeCashSale)
                .filter(
                    AirtimeCashSale.phone == parsed_sender,
                    AirtimeCashSale.amount >= amount_min,
                    AirtimeCashSale.amount <= amount_max,
                    AirtimeCashSale.status.in_(
                        ("pending", "submitted", "manual_review", "verified")
                    ),
                )
                .order_by(AirtimeCashSale.created_at.desc())
            )
            matched_sale = result.scalars().first()

        sms_log = AirtimeCashSmsLog(
            sender=payload.sender or parsed_sender,
            message=payload.message,
            parsed_sender=parsed_sender,
            parsed_amount=parsed_amount,
            matched_sale_id=matched_sale.id if matched_sale else None,
        )
        if payload.received_at:
            sms_log.received_at = payload.received_at
        db.add(sms_log)

        if matched_sale and matched_sale.status not in {"paid", "payout_pending"}:
            metadata = _parse_metadata_json(matched_sale.metadata_json)
            metadata["sms_message"] = payload.message
            metadata["sms_received_at"] = (
                payload.received_at.isoformat()
                if payload.received_at
                else datetime.now(timezone.utc).isoformat()
            )

            requires_review = bool(metadata.get("requires_manual_review")) or (
                matched_sale.amount >= AIRTIME_CASH_MANUAL_REVIEW_THRESHOLD
            )

            if requires_review:
                matched_sale.status = "manual_review"
                matched_sale.verified_at = datetime.now(timezone.utc)
                matched_sale.metadata_json = json.dumps(metadata)
                db.add(matched_sale)
                normalized_matched_phone = normalize_ghana_number(matched_sale.phone)
                await notification_service.send_sms(
                    normalized_matched_phone or matched_sale.phone,
                    f"CyberCash: Airtime received for {matched_sale.currency} {matched_sale.amount:.2f}. "
                    "Manual review is required before payout.",
                )
            else:
                matched_sale.status = "verified"
                matched_sale.verified_at = datetime.now(timezone.utc)
                await _trigger_airtime_cash_payout(matched_sale, metadata, db)
                payout_text = (
                    f"CyberCash: Airtime verified. Payout processing for {matched_sale.currency} "
                    f"{matched_sale.payout_amount:.2f}."
                )
                if matched_sale.status == "paid":
                    payout_text = (
                        f"CyberCash: {matched_sale.currency} {matched_sale.payout_amount:.2f} "
                        "has been sent to your MoMo wallet."
                    )
                elif matched_sale.status == "failed":
                    payout_text = (
                        "CyberCash: Payout failed. Please contact support or try again."
                    )
                normalized_matched_phone = normalize_ghana_number(matched_sale.phone)
                await notification_service.send_sms(normalized_matched_phone or matched_sale.phone, payout_text)

        await db.commit()
        return {"status": "ok", "matched_sale_id": matched_sale.id if matched_sale else None}
    finally:
        await db.close()
