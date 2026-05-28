import json
import uuid
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.database import get_db
from backend.dependencies.auth import get_current_user
from backend.models import Payment, Transaction, User, Wallet


router = APIRouter(prefix="/api/wallet/topup/paystack", tags=["Wallet Top-up"])
alias_router = APIRouter(tags=["Wallet Top-up"])


class PaystackWalletTopupRequest(BaseModel):
    amount: float = Field(..., gt=0)
    email: str | None = Field(default=None, max_length=255)


def _metadata(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _fallback_email(user: User) -> str:
    email = str(getattr(user, "email", "") or "").strip()
    if "@" in email:
        return email
    domain = str(getattr(settings, "PAYSTACK_FALLBACK_EMAIL_DOMAIN", "cybercash.app") or "cybercash.app").strip()
    return f"user{getattr(user, 'id', 'wallet')}@{domain}"


def _paystack_headers() -> dict[str, str]:
    secret_key = str(getattr(settings, "PAYSTACK_SECRET_KEY", "") or "").strip()
    if not secret_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Paystack is not configured. Set PAYSTACK_SECRET_KEY.",
        )
    return {
        "Authorization": f"Bearer {secret_key}",
        "Content-Type": "application/json",
    }


def _paystack_url(path: str) -> str:
    base_url = str(getattr(settings, "PAYSTACK_BASE_URL", "https://api.paystack.co") or "").rstrip("/")
    return f"{base_url}/{path.strip('/')}"


async def _get_or_create_wallet(db: AsyncSession, user_id: int) -> Wallet:
    result = await db.execute(select(Wallet).filter(Wallet.user_id == user_id))
    wallet = result.scalars().first()
    if wallet:
        return wallet
    wallet = Wallet(user_id=user_id, balance=0.0)
    db.add(wallet)
    await db.flush()
    return wallet


async def _initialize_paystack_payment(*, user: User, amount: float, email: str, reference: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "email": email,
        "amount": int(round(float(amount) * 100)),
        "currency": "GHS",
        "reference": reference,
        "channels": ["card", "mobile_money"],
        "metadata": {
            "user_id": getattr(user, "id", None),
            "purpose": "wallet_topup",
            "wallet_credit_currency": "GHS",
        },
    }
    callback_url = str(getattr(settings, "PAYSTACK_WALLET_CALLBACK_URL", "") or "").strip()
    if callback_url:
        payload["callback_url"] = callback_url

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(20.0)) as client:
            response = await client.post(_paystack_url("/transaction/initialize"), json=payload, headers=_paystack_headers())
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Paystack request timed out.") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Unable to reach Paystack.") from exc

    try:
        data = response.json() if response.headers.get("content-type", "").lower().startswith("application/json") else {}
    except ValueError:
        data = {}
    if response.status_code >= 400 or not isinstance(data, dict) or not data.get("status"):
        detail = "Unable to initialize Paystack payment."
        if isinstance(data, dict):
            detail = str(data.get("message") or detail)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail)
    return data


async def _verify_paystack(reference: str) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(20.0)) as client:
            response = await client.get(
                _paystack_url(f"/transaction/verify/{reference}"),
                headers=_paystack_headers(),
            )
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Paystack verification timed out.") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Unable to verify Paystack payment.") from exc

    try:
        data = response.json() if response.headers.get("content-type", "").lower().startswith("application/json") else {}
    except ValueError:
        data = {}
    if response.status_code >= 400 or not isinstance(data, dict):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Paystack verification failed.")
    return data


async def _credit_wallet_from_verified_payment(db: AsyncSession, *, reference: str, current_user: User | None = None) -> dict[str, Any]:
    verify_payload = await _verify_paystack(reference)
    paystack_data = verify_payload.get("data") if isinstance(verify_payload.get("data"), dict) else {}
    paid_status = str(paystack_data.get("status") or "").strip().lower()
    if paid_status != "success":
        return {
            "status": "pending",
            "message": "Payment has not been completed yet.",
            "reference": reference,
            "provider_response": verify_payload,
        }

    result = await db.execute(select(Payment).filter(Payment.our_transaction_id == reference))
    payment = result.scalars().first()

    user_id = getattr(current_user, "id", None)
    if payment:
        user_id = payment.user_id
    if not user_id:
        provider_meta = paystack_data.get("metadata") if isinstance(paystack_data.get("metadata"), dict) else {}
        try:
            user_id = int(provider_meta.get("user_id"))
        except Exception:
            user_id = None
    if not user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unable to match payment to a CyberCash user.")
    if current_user and int(user_id) != int(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This payment belongs to another account.")

    amount = round(float(paystack_data.get("amount") or 0) / 100.0, 2)
    if amount <= 0 and payment:
        amount = round(float(payment.amount or 0.0), 2)
    if amount <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Paystack returned an invalid amount.")

    processor_reference = str(paystack_data.get("reference") or reference)
    metadata = _metadata(getattr(payment, "metadata_json", None)) if payment else {}
    if metadata.get("wallet_credited") is True:
        wallet = await _get_or_create_wallet(db, int(user_id))
        return {
            "status": "success",
            "message": "Wallet was already credited.",
            "reference": reference,
            "wallet_balance": round(float(wallet.balance or 0.0), 2),
            "provider_response": verify_payload,
        }

    wallet = await _get_or_create_wallet(db, int(user_id))
    wallet.balance = round(float(wallet.balance or 0.0) + amount, 2)

    if not payment:
        payment = Payment(
            user_id=int(user_id),
            processor="paystack",
            type="wallet_topup",
            amount=amount,
            currency="GHS",
            status="successful",
            our_transaction_id=reference,
            processor_transaction_id=processor_reference,
        )
    payment.status = "successful"
    payment.processor_transaction_id = processor_reference
    metadata.update(
        {
            "wallet_credited": True,
            "wallet_credit_amount": amount,
            "paystack_status": paid_status,
            "paystack_reference": processor_reference,
            "paystack_verify_response": verify_payload,
        }
    )
    payment.metadata_json = json.dumps(metadata)

    db.add(payment)
    await db.flush()

    transaction = Transaction(
        user_id=int(user_id),
        wallet_id=wallet.id,
        type="wallet_topup",
        amount=amount,
        currency="GHS",
        status="completed",
        provider="paystack",
        provider_reference=processor_reference,
        metadata_json=json.dumps({"payment_id": payment.id, "paystack_reference": processor_reference}),
    )

    db.add(wallet)
    db.add(transaction)
    await db.commit()

    return {
        "status": "success",
        "message": "Wallet credited successfully.",
        "reference": reference,
        "amount": amount,
        "wallet_balance": round(float(wallet.balance or 0.0), 2),
        "provider_response": verify_payload,
    }


@router.post("/initialize", status_code=status.HTTP_201_CREATED)
async def initialize_wallet_topup(
    request: PaystackWalletTopupRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        amount = round(float(request.amount), 2)
        min_amount = float(getattr(settings, "PAYSTACK_MIN_WALLET_TOPUP_GHS", 1.0) or 1.0)
        max_amount = float(getattr(settings, "PAYSTACK_MAX_WALLET_TOPUP_GHS", 10000.0) or 10000.0)
        if amount < min_amount:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Minimum wallet top-up is GHS {min_amount:.2f}.")
        if amount > max_amount:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Maximum wallet top-up is GHS {max_amount:.2f}.")

        wallet = await _get_or_create_wallet(db, current_user.id)
        reference = f"CC_WALLET_{current_user.id}_{uuid.uuid4().hex[:18]}"
        email = str(request.email or "").strip() or _fallback_email(current_user)

        init_payload = await _initialize_paystack_payment(
            user=current_user,
            amount=amount,
            email=email,
            reference=reference,
        )
        paystack_data = init_payload.get("data") if isinstance(init_payload.get("data"), dict) else {}

        payment = Payment(
            user_id=current_user.id,
            processor="paystack",
            type="wallet_topup",
            amount=amount,
            currency="GHS",
            status="pending",
            our_transaction_id=reference,
            processor_transaction_id=str(paystack_data.get("reference") or reference),
            metadata_json=json.dumps(
                {
                    "wallet_id": wallet.id,
                    "wallet_credited": False,
                    "authorization_url": paystack_data.get("authorization_url"),
                    "access_code": paystack_data.get("access_code"),
                    "paystack_initialize_response": init_payload,
                }
            ),
        )
        db.add(payment)
        await db.commit()

        return {
            "status": "pending",
            "message": "Open the secure Paystack checkout to complete your wallet top-up.",
            "reference": reference,
            "amount": amount,
            "currency": "GHS",
            "authorization_url": paystack_data.get("authorization_url"),
            "access_code": paystack_data.get("access_code"),
        }
    finally:
        await db.close()


@router.get("/verify/{reference}")
async def verify_wallet_topup(
    reference: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await _credit_wallet_from_verified_payment(db, reference=reference.strip(), current_user=current_user)
    finally:
        await db.close()


@router.get("/verify")
async def verify_wallet_topup_by_query(
    reference: str = Query(..., min_length=6),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await verify_wallet_topup(reference=reference, db=db, current_user=current_user)


@router.get("/callback", response_class=HTMLResponse)
async def wallet_topup_callback(
    reference: str = Query(..., min_length=6),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await _credit_wallet_from_verified_payment(db, reference=reference.strip(), current_user=None)
        success = result.get("status") == "success"
        title = "Wallet top-up complete" if success else "Payment pending"
        message = result.get("message") or "Return to CyberCash to continue."
        balance = result.get("wallet_balance")
        balance_html = f"<p><strong>Wallet balance:</strong> GHS {balance:,.2f}</p>" if isinstance(balance, (int, float)) else ""
        return HTMLResponse(
            f"""
            <!doctype html>
            <html>
              <head>
                <meta name="viewport" content="width=device-width, initial-scale=1" />
                <title>{title}</title>
                <style>
                  body {{ font-family: Arial, sans-serif; background: #080b0f; color: #f3f5f7; margin: 0; padding: 24px; }}
                  main {{ max-width: 520px; margin: 12vh auto; }}
                  h1 {{ color: #efc96f; font-size: 28px; }}
                  p {{ color: #c9ced6; line-height: 1.5; }}
                </style>
              </head>
              <body>
                <main>
                  <h1>{title}</h1>
                  <p>{message}</p>
                  {balance_html}
                  <p>You can return to the CyberCash app now.</p>
                </main>
              </body>
            </html>
            """
        )
    finally:
        await db.close()


@alias_router.post("/api/paystack/wallet/initialize", status_code=status.HTTP_201_CREATED)
@alias_router.post("/api/paystack/wallet-topup/initialize", status_code=status.HTTP_201_CREATED)
@alias_router.post("/api/paystack/initialize-wallet-topup", status_code=status.HTTP_201_CREATED)
async def initialize_wallet_topup_alias(
    request: PaystackWalletTopupRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await initialize_wallet_topup(request=request, db=db, current_user=current_user)


@alias_router.get("/api/paystack/wallet/verify/{reference}")
@alias_router.get("/api/paystack/wallet-topup/verify/{reference}")
@alias_router.get("/api/paystack/verify-wallet-topup/{reference}")
async def verify_wallet_topup_alias(
    reference: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await verify_wallet_topup(reference=reference, db=db, current_user=current_user)


@alias_router.get("/api/paystack/wallet/verify")
@alias_router.get("/api/paystack/wallet-topup/verify")
@alias_router.get("/api/paystack/verify-wallet-topup")
async def verify_wallet_topup_query_alias(
    reference: str = Query(..., min_length=6),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await verify_wallet_topup(reference=reference, db=db, current_user=current_user)


@alias_router.get("/api/paystack/wallet/callback", response_class=HTMLResponse)
@alias_router.get("/api/paystack/wallet-topup/callback", response_class=HTMLResponse)
async def wallet_topup_callback_alias(
    reference: str = Query(..., min_length=6),
    db: AsyncSession = Depends(get_db),
):
    return await wallet_topup_callback(reference=reference, db=db)
