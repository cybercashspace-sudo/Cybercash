from __future__ import annotations

import hashlib
import json
import re
import secrets
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.transaction_types import TransactionType
from backend.database import get_db
from backend.dependencies.auth import get_current_user
from backend.models import Agent, AgentAPIKey, Transaction, User, Wallet
from backend.schemas.agent_api import (
    AgentCheckoutRequest,
    AgentCheckoutResponse,
    CreateAgentAPIKeyRequest,
)
from backend.services.paystack_service import PaystackService, get_paystack_service


router = APIRouter(tags=["Agent API"])
agent_api = APIRouter(prefix="/agent-api/v1", tags=["Agent Payment API"])
MAX_ACTIVE_KEYS_PER_AGENT = 5
MIN_CHECKOUT_GHS = Decimal("1.00")
MAX_CHECKOUT_GHS = Decimal("10000.00")
GHS_QUANTIZER = Decimal("0.01")
EMAIL_PATTERN = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s]{2,63}$")


def _key_digest(value: str) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def _safe_key_record(key: AgentAPIKey) -> dict:
    return {
        "id": key.id,
        "name": key.name,
        "mode": str(getattr(key, "mode", "live") or "live"),
        "public_key": str(getattr(key, "public_key", "") or ""),
        "prefix": key.key_prefix,
        "created_at": key.created_at.isoformat() if key.created_at else None,
        "last_used_at": key.last_used_at.isoformat() if key.last_used_at else None,
        "revoked": key.revoked_at is not None,
    }


async def _active_agent(db: AsyncSession, user_id: int, *, lock: bool = False) -> Agent:
    query = select(Agent).where(Agent.user_id == user_id)
    if lock:
        query = query.with_for_update()
    result = await db.execute(query)
    agent = result.scalars().first()
    if not agent:
        raise HTTPException(status_code=403, detail="An approved Agent account is required.")
    if str(agent.status or "").strip().lower() != "active":
        raise HTTPException(status_code=403, detail="API access is available after Agent approval.")
    owner_result = await db.execute(select(User).where(User.id == user_id))
    owner = owner_result.scalars().first()
    if owner is None or not bool(owner.is_active) or not bool(owner.is_verified):
        raise HTTPException(status_code=403, detail="Verify and activate your account before managing API keys.")
    return agent


async def _authenticate_api_key(
    db: AsyncSession,
    raw_key: str,
    *,
    lock_key: bool = False,
) -> tuple[AgentAPIKey, Agent]:
    value = str(raw_key or "").strip()
    if len(value) < 40 or len(value) > 120 or not value.startswith("cc_agent_"):
        raise HTTPException(status_code=401, detail="A valid CyberCash API key is required.")

    query = select(AgentAPIKey).where(
            AgentAPIKey.key_hash == _key_digest(value),
            AgentAPIKey.revoked_at.is_(None),
        )
    if lock_key:
        query = query.with_for_update()
    result = await db.execute(query)
    api_key = result.scalars().first()
    if api_key is None:
        raise HTTPException(status_code=401, detail="A valid CyberCash API key is required.")

    agent_result = await db.execute(select(Agent).where(Agent.id == api_key.agent_id))
    agent = agent_result.scalars().first()
    if agent is None or str(agent.status or "").strip().lower() != "active":
        raise HTTPException(status_code=403, detail="API access is unavailable for this Agent account.")
    owner_result = await db.execute(select(User).where(User.id == agent.user_id))
    owner = owner_result.scalars().first()
    if owner is None or not bool(owner.is_active) or not bool(owner.is_verified):
        raise HTTPException(status_code=403, detail="API access is unavailable for this account.")
    api_key.last_used_at = datetime.now(timezone.utc)
    return api_key, agent


@router.get("/agents/me/api-keys")
async def list_my_api_keys(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        agent = await _active_agent(db, current_user.id)
        result = await db.execute(
            select(AgentAPIKey)
            .where(AgentAPIKey.agent_id == agent.id)
            .order_by(AgentAPIKey.id.desc())
        )
        return {"items": [_safe_key_record(key) for key in result.scalars().all()]}
    finally:
        await db.close()


@router.post("/agents/me/api-keys", status_code=201)
async def create_my_api_key(
    request: CreateAgentAPIKeyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        agent = await _active_agent(db, current_user.id, lock=True)
        result = await db.execute(
            select(func.count(AgentAPIKey.id)).where(
                AgentAPIKey.agent_id == agent.id,
                AgentAPIKey.revoked_at.is_(None),
            )
        )
        if int(result.scalar_one() or 0) >= MAX_ACTIVE_KEYS_PER_AGENT:
            raise HTTPException(
                status_code=409,
                detail=f"You can have up to {MAX_ACTIVE_KEYS_PER_AGENT} active API keys. Revoke one before creating another.",
            )

        name = request.name.strip()
        if len(name) < 2:
            raise HTTPException(status_code=422, detail="API key name must contain at least 2 characters.")
        mode = request.mode
        raw_key = f"cc_agent_{mode}_" + secrets.token_urlsafe(32)
        public_key = "cc_pub_" + secrets.token_urlsafe(18)
        api_key = AgentAPIKey(
            agent_id=agent.id,
            name=name,
            mode=mode,
            public_key=public_key,
            key_prefix=raw_key[:24],
            key_hash=_key_digest(raw_key),
        )
        db.add(api_key)
        await db.commit()
        await db.refresh(api_key)
        return {
            **_safe_key_record(api_key),
            "api_key": raw_key,
            "message": "Copy this secret key now. It cannot be shown again.",
        }
    finally:
        await db.close()


@router.delete("/agents/me/api-keys/{key_id}")
async def revoke_my_api_key(
    key_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        agent = await _active_agent(db, current_user.id)
        result = await db.execute(
            select(AgentAPIKey).where(AgentAPIKey.id == key_id, AgentAPIKey.agent_id == agent.id)
        )
        api_key = result.scalars().first()
        if api_key is None:
            raise HTTPException(status_code=404, detail="API key not found.")
        if api_key.revoked_at is None:
            api_key.revoked_at = datetime.now(timezone.utc)
            await db.commit()
        return {"message": "API key revoked."}
    finally:
        await db.close()


@agent_api.post("/payments/checkout", response_model=AgentCheckoutResponse, status_code=201)
async def create_customer_checkout(
    request: AgentCheckoutRequest,
    http_request: Request,
    api_key_value: str = Header(..., alias="X-CyberCash-API-Key", min_length=40, max_length=120),
    idempotency_header: str = Header(..., alias="Idempotency-Key", min_length=8, max_length=128),
    db: AsyncSession = Depends(get_db),
    paystack_service: PaystackService = Depends(get_paystack_service),
):
    try:
        api_key, agent = await _authenticate_api_key(db, api_key_value, lock_key=True)
        submitted_amount = Decimal(request.amount)
        amount = submitted_amount.quantize(GHS_QUANTIZER, rounding=ROUND_HALF_UP)
        if submitted_amount != amount:
            raise HTTPException(status_code=422, detail="Amount can include up to 2 decimal places.")
        email = request.customer_email.strip().lower()
        customer_email_hash = _key_digest(email)
        if amount < MIN_CHECKOUT_GHS or amount > MAX_CHECKOUT_GHS:
            raise HTTPException(status_code=422, detail="Amount must be between GHS 1.00 and GHS 10,000.00.")
        if not EMAIL_PATTERN.fullmatch(email):
            raise HTTPException(status_code=422, detail="Enter a valid customer email address.")

        idem_source = str(idempotency_header or "").strip()
        if not idem_source or any(ord(ch) < 33 or ord(ch) > 126 for ch in idem_source):
            raise HTTPException(status_code=400, detail="Provide a valid Idempotency-Key header.")
        internal_idem = _key_digest(f"agent-api:{api_key.id}:{idem_source}")

        result = await db.execute(
            select(Transaction).where(Transaction.idempotency_key == internal_idem)
        )
        existing = result.scalars().first()
        if existing is not None:
            metadata = _read_metadata(existing.metadata_json)
            if Decimal(str(existing.amount)).quantize(GHS_QUANTIZER) != amount or metadata.get("customer_email_hash") != customer_email_hash:
                raise HTTPException(status_code=409, detail="This Idempotency-Key was already used for a different checkout.")
            is_test = str(metadata.get("environment") or "live") == "test"
            checkout_url = str(metadata.get("authorization_url") or "")
            if not is_test and not checkout_url:
                raise HTTPException(status_code=409, detail="This checkout is already being processed. Check its status using the returned reference.")
            response = AgentCheckoutResponse(
                status=existing.status,
                reference=str(existing.provider_reference or ""),
                authorization_url=checkout_url or None,
                amount=amount,
            )
            await db.commit()
            return response

        wallet_result = await db.execute(select(Wallet).where(Wallet.user_id == agent.user_id))
        wallet = wallet_result.scalars().first()
        if wallet is None or bool(wallet.is_deleted):
            raise HTTPException(status_code=409, detail="The Agent wallet is not ready to receive payments.")
        if bool(wallet.is_frozen):
            raise HTTPException(status_code=403, detail="This wallet cannot accept payments right now. Contact CyberCash support.")

        is_test = api_key.mode == "test"
        if is_test:
            # Test credentials are isolated from Paystack and wallet crediting.
            reference = "CC-TEST-" + secrets.token_hex(12)
            checkout_url = ""
            checkout_status = "test"
            provider = "cybercash_test"
        else:
            callback_url = str(http_request.url_for("paystack_checkout_status"))
            amount_subunit = int((amount * 100).to_integral_value(rounding=ROUND_HALF_UP))
            try:
                provider_result = await paystack_service.initiate_payment(
                    email=email,
                    amount=amount_subunit,
                    currency="GHS",
                    metadata={
                        "user_id": str(agent.user_id),
                        "agent_id": str(agent.id),
                        "agent_api_key_id": str(api_key.id),
                        "purpose": "agent_customer_payment",
                        "idempotency_key": internal_idem,
                    },
                    callback_url=callback_url,
                )
            except HTTPException as exc:
                raise HTTPException(status_code=502, detail="The payment provider could not start checkout. Please try again.") from exc
            except Exception as exc:
                raise HTTPException(status_code=502, detail="The payment provider could not start checkout. Please try again.") from exc

            reference = str(provider_result.get("reference") or "").strip()
            checkout_url = str(provider_result.get("authorization_url") or "").strip()
            if not reference or not checkout_url:
                raise HTTPException(status_code=502, detail="The payment provider returned an incomplete checkout. Please try again.")
            checkout_status = "pending"
            provider = "paystack"

        transaction = Transaction(
            user_id=agent.user_id,
            agent_id=agent.id,
            wallet_id=wallet.id,
            type=TransactionType.FUNDING,
            entry_type="credit",
            amount=amount,
            currency="GHS",
            status=checkout_status,
            provider=provider,
            provider_reference=reference,
            idempotency_key=internal_idem,
            metadata_json=json.dumps({
                "purpose": "agent_customer_payment",
                "environment": "test" if is_test else "live",
                "agent_api_key_id": api_key.id,
                "customer_email_hash": customer_email_hash,
                "authorization_url": checkout_url,
                "idempotency_key": internal_idem,
            }),
        )
        db.add(transaction)
        await db.commit()
        return AgentCheckoutResponse(
            status=checkout_status,
            reference=reference,
            authorization_url=checkout_url or None,
            amount=amount,
        )
    finally:
        await db.close()


@agent_api.get("/payments/{reference}")
async def get_customer_checkout_status(
    reference: str,
    api_key_value: str = Header(..., alias="X-CyberCash-API-Key", min_length=40, max_length=120),
    db: AsyncSession = Depends(get_db),
):
    try:
        api_key, agent = await _authenticate_api_key(db, api_key_value)
        result = await db.execute(
            select(Transaction).where(
                Transaction.provider.in_(["paystack", "cybercash_test"]),
                Transaction.provider_reference == reference,
                Transaction.user_id == agent.user_id,
                Transaction.agent_id == agent.id,
            )
        )
        transaction = result.scalars().first()
        if transaction is None:
            raise HTTPException(status_code=404, detail="Checkout reference not found.")
        metadata = _read_metadata(transaction.metadata_json)
        if metadata.get("agent_api_key_id") != api_key.id:
            raise HTTPException(status_code=404, detail="Checkout reference not found.")
        response = {
            "reference": reference,
            "status": transaction.status,
            "amount": str(transaction.amount),
            "currency": transaction.currency or "GHS",
            "environment": str(metadata.get("environment") or "live"),
        }
        await db.commit()
        return response
    finally:
        await db.close()


def _read_metadata(raw: str | None) -> dict:
    try:
        payload = json.loads(raw or "{}")
        return payload if isinstance(payload, dict) else {}
    except (TypeError, ValueError):
        return {}


router.include_router(agent_api)
