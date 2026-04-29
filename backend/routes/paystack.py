from html import escape

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession # Changed from Session
from sqlalchemy import select # New Import
from backend.database import get_db
from backend.dependencies.auth import get_current_user
from backend.models import User, Wallet, Transaction
from backend.schemas.paystack import (
    InitiatePaymentRequest, InitiatePaymentResponse, VerifyPaymentResponse
)
from backend.core.config import settings
from backend.services.paystack_service import (
    PaystackService,
    get_paystack_service,
    is_valid_paystack_signature,
)
from backend.services.transaction_engine import TransactionEngine, get_transaction_engine
from backend.core.transaction_types import TransactionType
import json # Import json
import os
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

router = APIRouter(prefix="/paystack", tags=["Paystack"])

MIN_PAYSTACK_DEPOSIT_GHS = Decimal("1.00")
GHS_QUANTIZER = Decimal("0.01")


def _checkout_status_url(request: Request, result: str) -> str:
    base_url = str(request.url_for("paystack_checkout_status")).strip()
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}result={str(result or '').strip().lower()}"


def _checkout_status_page(result: str, reference: str | None = None) -> str:
    result_key = str(result or "").strip().lower()
    is_cancelled = result_key == "cancelled"
    is_success = result_key == "success"

    if is_success:
        headline = "Payment confirmed"
        message = "Your payment was received. This window will close automatically."
        accent = "#44D19D"
    elif is_cancelled:
        headline = "Payment cancelled"
        message = "The checkout was cancelled. This window will close automatically."
        accent = "#F6A84C"
    else:
        headline = "Checkout complete"
        message = "You can close this window."
        accent = "#D4AF37"

    reference_line = f"<p class=\"reference\">Reference: {escape(reference)}</p>" if reference else ""

    return f"""<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta http-equiv="cache-control" content="no-store, no-cache, must-revalidate, max-age=0">
    <meta http-equiv="pragma" content="no-cache">
    <meta http-equiv="expires" content="0">
    <title>CYBER CASH Paystack</title>
    <style>
        :root {{
            color-scheme: dark;
            --bg: #07110d;
            --card: rgba(9, 20, 16, 0.94);
            --border: rgba(212, 175, 55, 0.16);
            --text: #eef2f4;
            --muted: #b4bbc2;
            --accent: {accent};
        }}
        html, body {{
            height: 100%;
            margin: 0;
            background:
                radial-gradient(circle at top, rgba(68, 209, 157, 0.18), transparent 30%),
                linear-gradient(180deg, #08110d 0%, #050807 100%);
            font-family: "Segoe UI", Arial, sans-serif;
            color: var(--text);
        }}
        body {{
            display: grid;
            place-items: center;
            padding: 24px;
            box-sizing: border-box;
        }}
        .card {{
            width: min(420px, 100%);
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 24px;
            box-shadow: 0 24px 80px rgba(0, 0, 0, 0.38);
            padding: 28px 24px;
            text-align: center;
            backdrop-filter: blur(18px);
        }}
        .badge {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 60px;
            height: 60px;
            border-radius: 18px;
            margin-bottom: 18px;
            background: rgba(212, 175, 55, 0.12);
            color: var(--accent);
            font-size: 28px;
            font-weight: 700;
        }}
        h1 {{
            margin: 0 0 10px;
            font-size: 26px;
            line-height: 1.15;
        }}
        p {{
            margin: 0;
            color: var(--muted);
            font-size: 15px;
            line-height: 1.6;
        }}
        .reference {{
            margin-top: 14px;
            font-size: 13px;
            color: #93a0aa;
            word-break: break-word;
        }}
    </style>
</head>
<body>
    <div class="card">
        <div class="badge">CC</div>
        <h1>{escape(headline)}</h1>
        <p>{escape(message)}</p>
        {reference_line}
    </div>
    <script>
        (function() {{
            var attempts = 0;
            function closeWindow() {{
                attempts += 1;
                try {{
                    if (window.pywebview && window.pywebview.api && window.pywebview.api.close_window) {{
                        window.pywebview.api.close_window();
                        return;
                    }}
                }} catch (err) {{}}
                if (attempts < 20) {{
                    setTimeout(closeWindow, 200);
                }}
            }}
            setTimeout(closeWindow, 400);
        }})();
    </script>
</body>
</html>"""


def _to_ghs_amount(value) -> Decimal:
    try:
        normalized = Decimal(str(value)).quantize(GHS_QUANTIZER, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid amount.")
    if normalized < MIN_PAYSTACK_DEPOSIT_GHS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Amount must be at least GHS 1.00.",
        )
    return normalized


def _kobo_to_ghs(value) -> Decimal:
    try:
        return (Decimal(str(value)) / Decimal("100")).quantize(GHS_QUANTIZER, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Paystack amount.")


async def _get_wallet_balance(db: AsyncSession, wallet_id: int) -> float:
    result = await db.execute(select(Wallet.balance).filter(Wallet.id == wallet_id))
    balance = result.scalar_one_or_none()
    try:
        return float(balance or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _resolve_paystack_email(current_user: User) -> str:
    email = str(current_user.email or "").strip().lower()
    if email and re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return email

    identity = str(current_user.momo_number or current_user.phone_number or "").strip()
    digits = "".join(ch for ch in identity if ch.isdigit())
    if not digits:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A valid email or phone number is required for Paystack deposit.",
        )

    domain = str(os.getenv("PAYSTACK_FALLBACK_EMAIL_DOMAIN", "cybercash.app") or "cybercash.app").strip().lower()
    if not domain:
        domain = "cybercash.app"
    return f"user{digits}@{domain}"

@router.post(
    "/initiate",
    response_model=InitiatePaymentResponse,
    responses={
        400: {"description": "Invalid request or Paystack rejected request."},
        401: {"description": "Not authenticated. Provide Bearer access token."},
        502: {"description": "Paystack service/network unavailable."},
    },
)
async def initiate_paystack_payment(
    request: InitiatePaymentRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    paystack_service: PaystackService = Depends(get_paystack_service)
):
    """
    Initiate a payment with Paystack.
    """
    try:
        amount_ghs = _to_ghs_amount(request.amount)
        amount_kobo = int((amount_ghs * 100).to_integral_value(rounding=ROUND_HALF_UP))
        
        # Check if user has a wallet
        result = await db.execute(select(Wallet).filter(Wallet.user_id == current_user.id))
        wallet = result.scalars().first()
        if not wallet:
            wallet = Wallet(user_id=current_user.id, currency="GHS", balance=0.0)
            db.add(wallet)
            await db.flush()

        try:
            checkout_callback_url = _checkout_status_url(http_request, "success")
            checkout_cancel_url = _checkout_status_url(http_request, "cancelled")
            payment_data = await paystack_service.initiate_payment(
                email=_resolve_paystack_email(current_user),
                amount=amount_kobo, # Paystack expects amount in kobo (cents)
                currency="GHS",
                metadata={
                    "user_id": str(current_user.id),
                    "purpose": "deposit",
                    "cancel_action": checkout_cancel_url,
                },
                callback_url=checkout_callback_url,
            )
            # Store a pending transaction in your DB
            transaction = Transaction(
                user_id=current_user.id,
                wallet_id=wallet.id,
                type=TransactionType.FUNDING,
                amount=float(amount_ghs),
                currency="GHS", # Assuming GHS, adjust if dynamic
                status="pending",
                provider="paystack",
                provider_reference=payment_data["reference"],
                metadata_json=json.dumps(
                    {
                        "authorization_url": payment_data["authorization_url"],
                        "callback_url": checkout_callback_url,
                        "cancel_action": checkout_cancel_url,
                    }
                ),
            )
            db.add(transaction)
            await db.commit()
            await db.refresh(transaction)

            return InitiatePaymentResponse(
                authorization_url=payment_data["authorization_url"],
                access_code=payment_data["access_code"],
                reference=payment_data["reference"]
            )
        except HTTPException as e:
            raise e
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Unable to start Paystack checkout right now. Please try again.",
            )
    finally:
        await db.close()


@router.get("/checkout/status", name="paystack_checkout_status", response_class=HTMLResponse)
async def paystack_checkout_status(result: str = "success", reference: str | None = None):
    """
    Friendly landing page for Paystack success/cancel redirects.
    """
    return HTMLResponse(content=_checkout_status_page(result=result, reference=reference))

@router.get(
    "/verify/{reference}",
    response_model=VerifyPaymentResponse,
    responses={
        400: {"description": "Payment not successful or amount mismatched."},
        401: {"description": "Not authenticated. Provide Bearer access token."},
        404: {"description": "Transaction reference not found for current user."},
        502: {"description": "Paystack service/network unavailable."},
    },
)
async def verify_paystack_payment(
    reference: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    paystack_service: PaystackService = Depends(get_paystack_service),
    transaction_engine: TransactionEngine = Depends(get_transaction_engine)
):
    """
    Verify a Paystack payment using its reference.
    """
    try:
        result = await db.execute(select(Transaction).filter(
            Transaction.user_id == current_user.id,
            Transaction.provider == "paystack",
            Transaction.provider_reference == reference,
            Transaction.type == TransactionType.FUNDING,
        ))
        transaction = result.scalars().first()

        if not transaction:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found or does not belong to user.")

        expected_amount = Decimal(str(transaction.amount)).quantize(GHS_QUANTIZER, rounding=ROUND_HALF_UP)
        
        if transaction.status == "completed":
            wallet_balance = await _get_wallet_balance(db, transaction.wallet_id)
            return VerifyPaymentResponse(
                status="success",
                message="Payment already completed. Your wallet has been credited.",
                credited_amount=float(expected_amount),
                wallet_balance=wallet_balance,
            )

        try:
            verification_data = await paystack_service.verify_payment(reference)
            paystack_status = str(verification_data.get("status", "")).strip().lower()
            paystack_amount = _kobo_to_ghs(verification_data.get("amount"))

            if paystack_status == "success":
                if paystack_amount != expected_amount:
                    transaction.status = "failed"
                    db.add(transaction)
                    await db.commit()
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Payment verification failed due to amount mismatch.",
                    )

                # Use TransactionEngine to finalize
                try:
                    if transaction.status != "pending":
                        transaction.status = "pending"
                        db.add(transaction)
                        await db.flush()
                    await transaction_engine.confirm_transaction(transaction.id)
                except ValueError:
                    await db.refresh(transaction)
                    if transaction.status != "completed":
                        raise
                wallet_balance = await _get_wallet_balance(db, transaction.wallet_id)
                return VerifyPaymentResponse(
                    status="success",
                    message=f"Payment successful. GHS {expected_amount:.2f} was credited to your wallet.",
                    credited_amount=float(expected_amount),
                    wallet_balance=wallet_balance,
                )

            if paystack_status in {"pending", "ongoing", "processing", "queued"}:
                return VerifyPaymentResponse(
                    status="pending",
                    message="Payment is still processing. Your wallet will be credited immediately once confirmed.",
                )

            if paystack_status == "abandoned":
                return VerifyPaymentResponse(
                    status="pending",
                    message=(
                        "We have not received final confirmation for this Paystack payment yet. "
                        "If you completed payment, please wait a moment and tap Check Status again - "
                        "your wallet will be credited automatically once Paystack confirms. "
                        "If you did not complete payment, please start a new deposit to get a new reference."
                    ),
                )

            transaction.status = "failed"
            db.add(transaction)
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Payment verification failed: {paystack_status or 'unknown'}",
            )
        except HTTPException as e:
            raise e
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Unable to verify Paystack payment right now. Please try again.",
            )
    finally:
        await db.close()

@router.post("/webhook")
async def paystack_webhook(
    request: Request, 
    db: AsyncSession = Depends(get_db),
    transaction_engine: TransactionEngine = Depends(get_transaction_engine)
):
    """
    Endpoint for Paystack webhooks to notify about transaction updates.
    """
    try:
        # Verify webhook signature
        paystack_signature = request.headers.get("x-paystack-signature")
        if not paystack_signature:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No signature provided.")

        request_body = await request.body()
        if not is_valid_paystack_signature(paystack_signature, request_body):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook signature.")

        event = json.loads(request_body)
        event_type = event.get("event")
        data = event.get("data")

        if event_type == "charge.success":
            reference = data.get("reference")
            amount_kobo = data.get("amount")
            amount_ghs = _kobo_to_ghs(amount_kobo)
            status_paystack = data.get("status")

            result = await db.execute(select(Transaction).filter(
                Transaction.provider == "paystack",
                Transaction.provider_reference == reference,
                Transaction.type == TransactionType.FUNDING,
            ))
            transaction = result.scalars().first()
            expected_amount = Decimal(str(transaction.amount)).quantize(GHS_QUANTIZER, rounding=ROUND_HALF_UP) if transaction else None

            if not transaction:
                return {"message": "Webhook processed: Transaction not found."}

            if transaction.status == "completed":
                return {"message": "Webhook processed: Payment already completed."}

            if status_paystack == "success" and amount_ghs == expected_amount:
                try:
                    if transaction.status != "pending":
                        transaction.status = "pending"
                        db.add(transaction)
                        await db.flush()
                    await transaction_engine.confirm_transaction(transaction.id)
                except ValueError:
                    await db.refresh(transaction)
                    if transaction.status != "completed":
                        raise
                return {"message": "Webhook processed: Payment completed and wallet updated."}

            transaction.status = "failed"
            db.add(transaction)
            await db.commit()
            return {"message": f"Webhook processed: Payment {status_paystack}."}
        
        return {"message": f"Webhook received, event type: {event_type}"}
    finally:
        await db.close()
