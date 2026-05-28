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
from backend.services.paystack_fulfillment import (
    AGENT_REGISTRATION_TX_TYPE,
    PAYSTACK_PENDING_STATUSES,
    complete_paid_agent_registration,
    paystack_currency_matches,
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


def _checkout_status_page(
    result: str,
    reference: str | None = None,
    message_override: str | None = None,
    wallet_balance: float | None = None,
) -> str:
    result_key = str(result or "").strip().lower()
    is_cancelled = result_key == "cancelled"
    is_success = result_key == "success"
    is_failed = result_key == "failed"

    if is_success:
        headline = "Wallet top-up complete"
        message = "Your payment was received and your wallet was updated. Return to CyberCash to continue."
        accent = "#44D19D"
    elif is_failed:
        headline = "Payment not completed"
        message = "We could not confirm this payment. Return to CyberCash and try again."
        accent = "#FF6B6B"
    elif is_cancelled:
        headline = "Payment cancelled"
        message = "The checkout was cancelled. Return to CyberCash when you are ready to try again."
        accent = "#F6A84C"
    else:
        headline = "Payment still processing"
        message = "We are still waiting for Paystack confirmation. Return to CyberCash and tap Check Status."
        accent = "#D4AF37"

    if message_override:
        message = str(message_override)
    reference_line = f"<p class=\"reference\">Reference: {escape(reference)}</p>" if reference else ""
    balance_line = (
        f"<p class=\"balance\"><strong>Wallet balance:</strong> GHS {wallet_balance:,.2f}</p>"
        if isinstance(wallet_balance, (int, float))
        else ""
    )

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
        .balance {{
            margin-top: 14px;
            color: #eef2f4;
            font-size: 15px;
        }}
    </style>
</head>
<body>
    <div class="card">
        <div class="badge">CC</div>
        <h1>{escape(headline)}</h1>
        <p>{escape(message)}</p>
        {balance_line}
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


async def _get_user_wallet_balance(db: AsyncSession, user_id: int) -> float:
    result = await db.execute(select(Wallet.balance).filter(Wallet.user_id == user_id))
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


def _expected_transaction_amount(transaction: Transaction) -> Decimal:
    return Decimal(str(transaction.amount)).quantize(GHS_QUANTIZER, rounding=ROUND_HALF_UP)


def _validate_successful_paystack_payload(transaction: Transaction, verification_data: dict) -> Decimal:
    expected_amount = _expected_transaction_amount(transaction)
    paystack_amount = _kobo_to_ghs(verification_data.get("amount"))
    if paystack_amount != expected_amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment verification failed due to amount mismatch.",
        )

    if not paystack_currency_matches(verification_data.get("currency"), transaction.currency or "GHS"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment verification failed due to currency mismatch.",
        )

    return expected_amount


async def _complete_paystack_wallet_funding(
    db: AsyncSession,
    transaction: Transaction,
    transaction_engine: TransactionEngine,
) -> None:
    if transaction.status != "pending":
        transaction.status = "pending"
        db.add(transaction)
        await db.flush()
    try:
        await transaction_engine.confirm_transaction(transaction.id)
    except ValueError:
        await db.refresh(transaction)
        if transaction.status != "completed":
            raise

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
async def paystack_checkout_status(
    result: str = "success",
    reference: str | None = None,
    db: AsyncSession = Depends(get_db),
    paystack_service: PaystackService = Depends(get_paystack_service),
    transaction_engine: TransactionEngine = Depends(get_transaction_engine),
):
    """
    Friendly landing page for Paystack success/cancel redirects.

    Paystack opens this URL outside the app too, so it also verifies and credits
    the matching wallet deposit when a reference is present.
    """
    try:
        cleaned_reference = str(reference or "").strip()
        if not cleaned_reference:
            return HTMLResponse(
                content=_checkout_status_page(
                    result=result,
                    message_override="Return to CyberCash. If your wallet does not update, tap Refresh Wallet.",
                )
            )

        transaction_result = await db.execute(
            select(Transaction).filter(
                Transaction.provider == "paystack",
                Transaction.provider_reference == cleaned_reference,
                Transaction.type == TransactionType.FUNDING,
            )
        )
        transaction = transaction_result.scalars().first()
        if not transaction:
            return HTMLResponse(
                content=_checkout_status_page(
                    result="pending",
                    reference=cleaned_reference,
                    message_override=(
                        "We received the Paystack redirect, but this reference is not linked to a wallet top-up yet. "
                        "Return to CyberCash and tap Refresh Wallet."
                    ),
                )
            )

        expected_amount = _expected_transaction_amount(transaction)
        if transaction.status == "completed":
            wallet_balance = await _get_wallet_balance(db, transaction.wallet_id)
            return HTMLResponse(
                content=_checkout_status_page(
                    result="success",
                    reference=cleaned_reference,
                    wallet_balance=wallet_balance,
                    message_override=f"GHS {expected_amount:.2f} was already credited to your wallet.",
                )
            )

        verification_data = await paystack_service.verify_payment(cleaned_reference)
        paystack_status = str(verification_data.get("status", "")).strip().lower()

        if paystack_status == "success":
            expected_amount = _validate_successful_paystack_payload(transaction, verification_data)
            await _complete_paystack_wallet_funding(db, transaction, transaction_engine)
            wallet_balance = await _get_wallet_balance(db, transaction.wallet_id)
            return HTMLResponse(
                content=_checkout_status_page(
                    result="success",
                    reference=cleaned_reference,
                    wallet_balance=wallet_balance,
                    message_override=f"GHS {expected_amount:.2f} was credited to your CyberCash wallet.",
                )
            )

        if paystack_status in PAYSTACK_PENDING_STATUSES:
            return HTMLResponse(
                content=_checkout_status_page(
                    result="pending",
                    reference=cleaned_reference,
                    message_override=(
                        "Paystack has not confirmed this payment yet. Return to CyberCash and tap Check Status."
                    ),
                )
            )

        transaction.status = "failed"
        db.add(transaction)
        await db.commit()
        return HTMLResponse(
            content=_checkout_status_page(
                result="failed",
                reference=cleaned_reference,
                message_override="Paystack did not complete this payment. Return to CyberCash and start a new deposit.",
            )
        )
    except HTTPException as exc:
        if getattr(exc, "status_code", 500) >= 500:
            page_result = "pending"
            message = "Paystack confirmation is temporarily unavailable. Return to CyberCash and tap Check Status."
        else:
            page_result = "failed"
            message = str(exc.detail or "We could not confirm this Paystack payment.")
        return HTMLResponse(
            content=_checkout_status_page(
                result=page_result,
                reference=str(reference or "").strip() or None,
                message_override=message,
            )
        )
    finally:
        await db.close()

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

        expected_amount = _expected_transaction_amount(transaction)
        
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

            if paystack_status == "success":
                try:
                    expected_amount = _validate_successful_paystack_payload(transaction, verification_data)
                except HTTPException:
                    transaction.status = "failed"
                    db.add(transaction)
                    await db.commit()
                    raise

                # Use TransactionEngine to finalize
                await _complete_paystack_wallet_funding(db, transaction, transaction_engine)
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


@router.post(
    "/recover",
    responses={
        401: {"description": "Not authenticated. Provide Bearer access token."},
        502: {"description": "Paystack service/network unavailable."},
    },
)
async def recover_paystack_deposits(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    paystack_service: PaystackService = Depends(get_paystack_service),
    transaction_engine: TransactionEngine = Depends(get_transaction_engine),
):
    """
    Reconcile pending Paystack wallet deposits for the signed-in user.
    This credits only transactions Paystack verifies as successful.
    """
    try:
        result = await db.execute(
            select(Transaction)
            .filter(
                Transaction.user_id == current_user.id,
                Transaction.provider == "paystack",
                Transaction.type == TransactionType.FUNDING,
                Transaction.status == "pending",
            )
            .order_by(Transaction.timestamp.desc())
            .limit(20)
        )
        pending_transactions = result.scalars().all()

        recovered_count = 0
        credited_amount = Decimal("0.00")
        pending_count = 0
        failed_count = 0
        recovered_references: list[str] = []

        for transaction in pending_transactions:
            reference = str(transaction.provider_reference or "").strip()
            if not reference:
                pending_count += 1
                continue

            try:
                verification_data = await paystack_service.verify_payment(reference)
            except HTTPException as exc:
                if exc.status_code >= 500:
                    raise
                transaction.status = "failed"
                db.add(transaction)
                await db.commit()
                failed_count += 1
                continue
            paystack_status = str(verification_data.get("status", "")).strip().lower()

            if paystack_status == "success":
                try:
                    expected_amount = _validate_successful_paystack_payload(transaction, verification_data)
                except HTTPException:
                    transaction.status = "failed"
                    db.add(transaction)
                    await db.commit()
                    failed_count += 1
                    continue

                await _complete_paystack_wallet_funding(db, transaction, transaction_engine)
                recovered_count += 1
                credited_amount += expected_amount
                recovered_references.append(reference)
                continue

            if paystack_status in PAYSTACK_PENDING_STATUSES:
                pending_count += 1
                continue

            transaction.status = "failed"
            db.add(transaction)
            await db.commit()
            failed_count += 1

        wallet_balance = await _get_user_wallet_balance(db, current_user.id)
        credited_amount = credited_amount.quantize(GHS_QUANTIZER, rounding=ROUND_HALF_UP)
        if recovered_count:
            message = (
                f"Recovered {recovered_count} Paystack deposit"
                f"{'' if recovered_count == 1 else 's'} and credited GHS {credited_amount:.2f}."
            )
            status_value = "success"
        elif pending_count:
            message = "No completed Paystack deposits found yet. Pending payments will credit once Paystack confirms."
            status_value = "pending"
        else:
            message = "No pending Paystack deposits found for this wallet."
            status_value = "idle"

        return {
            "status": status_value,
            "message": message,
            "recovered_count": recovered_count,
            "pending_count": pending_count,
            "failed_count": failed_count,
            "credited_amount": float(credited_amount),
            "wallet_balance": wallet_balance,
            "references": recovered_references,
        }
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
            if not isinstance(data, dict):
                return {"message": "Webhook processed: Missing charge data."}

            reference = data.get("reference")
            amount_kobo = data.get("amount")
            amount_ghs = _kobo_to_ghs(amount_kobo)
            status_paystack = str(data.get("status") or "").strip().lower()

            result = await db.execute(select(Transaction).filter(
                Transaction.provider == "paystack",
                Transaction.provider_reference == reference,
            ))
            transaction = result.scalars().first()
            expected_amount = Decimal(str(transaction.amount)).quantize(GHS_QUANTIZER, rounding=ROUND_HALF_UP) if transaction else None

            if not transaction:
                return {"message": "Webhook processed: Transaction not found."}

            if transaction.status == "completed":
                if transaction.type == AGENT_REGISTRATION_TX_TYPE:
                    await complete_paid_agent_registration(db, transaction)
                    return {"message": "Webhook processed: Agent registration already completed."}
                return {"message": "Webhook processed: Payment already completed."}

            currency_ok = paystack_currency_matches(data.get("currency"), transaction.currency or "GHS")
            if status_paystack == "success" and amount_ghs == expected_amount and currency_ok:
                if transaction.type == AGENT_REGISTRATION_TX_TYPE:
                    await complete_paid_agent_registration(db, transaction)
                    return {"message": "Webhook processed: Agent registration completed."}

                if transaction.type != TransactionType.FUNDING:
                    return {"message": f"Webhook processed: Unsupported Paystack transaction type {transaction.type}."}

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

            if status_paystack in PAYSTACK_PENDING_STATUSES:
                return {"message": "Webhook processed: Payment still pending."}

            transaction.status = "failed"
            db.add(transaction)
            await db.commit()
            return {"message": f"Webhook processed: Payment {status_paystack}."}
        
        return {"message": f"Webhook received, event type: {event_type}"}
    finally:
        await db.close()
