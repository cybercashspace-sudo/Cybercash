import logging
import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, or_, select

from backend.database import get_db
from backend.models.agent import Agent
from backend.models.user import User
from backend.models.wallet import Wallet
from backend.core.security import hash_password, verify_password, create_jwt
from backend.schemas.auth import (
    RegisterSchema,
    LoginSchema,
    TokenResponse,
    VerifyOtpSchema,
    ChangePinSchema,
    ResetPinSchema,
    ResetPinRequestSchema,
    AccessSchema,
    VerifySchema,
    ResendSchema,
    LookupNameSchema,
    LookupNameResponse,
)
from backend.schemas.user import UserResponse
from backend.services.compliance_service import ensure_daily_window, resolve_daily_limit_for_tier
from backend.services.otp_service import OTPService, get_otp_service
from backend.dependencies.auth import get_current_user
from utils.network import detect_network, normalize_ghana_number
from utils.security import hash_pin, verify_pin

router = APIRouter(prefix="/auth", tags=["AUTH"])

logger = logging.getLogger(__name__)

# In-memory rate limiter state (sufficient for single-process deployment).
_RATE_LIMIT_STATE: dict[str, list[datetime]] = {}
_RATE_LIMIT_WINDOW_SECONDS = 300
_RATE_LIMIT_MAX_ATTEMPTS = 5
_PIN_MAX_ATTEMPTS = 3
_PIN_LOCK_MINUTES = 5


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _to_aware(dt: datetime | None) -> datetime | None:
    if not dt:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _normalize_identity_number(raw_number: str | None) -> str:
    normalized = normalize_ghana_number(raw_number or "")
    if not normalized:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "momo_number is required")
    return normalized


def _normalize_device_id(raw_device_id: str | None) -> str:
    return str(raw_device_id or "").strip()


def _normalize_first_name(raw_first_name: str | None, fallback_name: str | None = None) -> str:
    candidate = str(raw_first_name or "").strip() or str(fallback_name or "").strip()
    if not candidate:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "first_name is required for new registrations")
    first_name = candidate.split()[0].strip()
    if not first_name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "first_name is required for new registrations")
    return first_name


def _safe_first_name_from_user(user: User | None) -> str:
    if not user:
        return ""
    first_name = str(getattr(user, "first_name", "") or "").strip()
    if first_name:
        return first_name
    full_name = str(user.full_name or "").strip()
    if not full_name:
        return ""
    return full_name.split()[0].strip()


def _with_debug_otp(payload: dict, otp_service: OTPService, otp_code: str | None) -> dict:
    """
    Expose OTP in API response only for local/log transport.
    """
    force_expose = str(os.getenv("EXPOSE_OTP_IN_API", "")).strip().lower() in {"1", "true", "yes", "on"}
    if otp_code and (force_expose or otp_service.provider == "log"):
        payload["debug_otp"] = str(otp_code)
    return payload


def _raise_if_otp_dispatch_failed(send_result: dict | None) -> None:
    if not isinstance(send_result, dict):
        return
    status_value = str(send_result.get("status", "") or "").strip().lower()
    if status_value != "error":
        return

    provider = str(send_result.get("provider", "") or "").strip().lower() or "unknown"
    detail = str(send_result.get("detail", "") or "").strip()
    env = str(os.getenv("ENV", "development") or "development").strip().lower()
    in_production = env in {"prod", "production"}

    logger.warning("OTP dispatch failed (provider=%s): %s", provider, detail or send_result)

    if in_production:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to send OTP right now. Please try again later.",
        )

    if detail:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Unable to send OTP via {provider}: {detail}")
    raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Unable to send OTP via {provider}.")


def revoke_user_tokens(user: User) -> None:
    user.token_version = int(user.token_version or 0) + 1


def _enforce_rate_limit(action: str, phone_number: str, ip_address: str | None = None) -> None:
    key = f"{action}:{phone_number}:{ip_address or 'unknown'}"
    now = _now_utc()
    window_start = now - timedelta(seconds=_RATE_LIMIT_WINDOW_SECONDS)
    attempts = _RATE_LIMIT_STATE.get(key, [])
    attempts = [ts for ts in attempts if ts >= window_start]
    if len(attempts) >= _RATE_LIMIT_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Please try again later.",
        )
    attempts.append(now)
    _RATE_LIMIT_STATE[key] = attempts


def _enforce_access_rate_limit(identity: str, ip_address: str | None = None) -> None:
    # 5 requests per minute per number.
    key = f"access:{identity}:{ip_address or 'unknown'}"
    now = _now_utc()
    window_start = now - timedelta(seconds=60)
    attempts = _RATE_LIMIT_STATE.get(key, [])
    attempts = [ts for ts in attempts if ts >= window_start]
    if len(attempts) >= 5:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many access attempts. Try again in a minute.",
        )
    attempts.append(now)
    _RATE_LIMIT_STATE[key] = attempts


async def _cleanup_stale_unverified(db: AsyncSession, momo_number: str) -> None:
    result = await db.execute(select(User).filter(User.momo_number == momo_number))
    user = result.scalars().first()
    if not user:
        return
    if user.is_verified:
        return
    created_at = _to_aware(user.created_at)
    if created_at and (_now_utc() - created_at) > timedelta(hours=24):
        await db.delete(user)
        await db.commit()


@router.post("/register/initiate")
async def register_initiate(
    data: RegisterSchema,
    request: Request,
    db: AsyncSession = Depends(get_db),
    otp_service: OTPService = Depends(get_otp_service),
):
    """Primary identity = mobile number, auth credential = 4-digit PIN, verification = OTP."""
    identity_number = _normalize_identity_number(data.momo_number or data.phone_number)
    normalized_email = str(data.email or "").strip().lower() or None
    first_name = _normalize_first_name(data.first_name, data.full_name)
    _enforce_rate_limit("register_initiate", identity_number, request.client.host if request.client else None)

    if normalized_email:
        existing_email_result = await db.execute(select(User).filter(func.lower(User.email) == normalized_email))
        existing_email_user = existing_email_result.scalars().first()
        if existing_email_user and existing_email_user.momo_number != identity_number:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Email already registered.")

    existing_phone_result = await db.execute(
        select(User).filter((User.phone_number == identity_number) | (User.momo_number == identity_number))
    )
    existing_user = existing_phone_result.scalars().first()
    if existing_user and existing_user.is_verified:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Phone number already registered")

    otp_expires = _now_utc() + timedelta(minutes=2)

    if existing_user:
        existing_user.full_name = first_name
        existing_user.email = normalized_email
        pin_hashed = hash_pin(data.pin)
        existing_user.password_hash = pin_hashed
        existing_user.pin_hash = pin_hashed
        existing_user.phone_number = identity_number
        existing_user.momo_number = identity_number
        existing_user.provider = detect_network(identity_number)
        existing_user.bound_device_id = data.device_id
        existing_user.first_login_fingerprint = data.device_fingerprint or existing_user.first_login_fingerprint
        existing_user.kyc_tier = existing_user.kyc_tier or 1
        existing_user.daily_limit = resolve_daily_limit_for_tier(existing_user.kyc_tier)
        ensure_daily_window(existing_user)
        existing_user.verification_token = "redis"
        existing_user.otp_expires_at = otp_expires
        existing_user.otp_attempt_count = 0
        existing_user.is_verified = False
        db.add(existing_user)
    else:
        pin_hashed = hash_pin(data.pin)
        user = User(
            full_name=first_name,
            email=normalized_email,
            phone_number=identity_number,
            momo_number=identity_number,
            provider=detect_network(identity_number),
            password_hash=pin_hashed,
            pin_hash=pin_hashed,
            is_verified=False,
            bound_device_id=data.device_id,
            first_login_fingerprint=data.device_fingerprint,
            is_agent=bool(data.is_agent),
            kyc_tier=1,
            daily_limit=resolve_daily_limit_for_tier(1),
            verification_token="redis",
            otp_expires_at=otp_expires,
            otp_attempt_count=0,
        )
        db.add(user)
        await db.flush()
        wallet = Wallet(user_id=user.id, currency="GHS", balance=0.0)
        db.add(wallet)
        if data.is_agent:
            if not data.business_name or not data.ghana_card_id or not data.agent_location:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    "Agent registration requires business_name, ghana_card_id, and agent_location.",
                )
            agent = Agent(
                user_id=user.id,
                status="pending",
                business_name=data.business_name,
                ghana_card_id=data.ghana_card_id,
                agent_location=data.agent_location,
            )
            db.add(agent)

    otp_code, send_result = await otp_service.issue_otp(identity_number)
    _raise_if_otp_dispatch_failed(send_result)
    await db.commit()
    return _with_debug_otp(
        {"message": "OTP sent. Verify to complete registration."},
        otp_service,
        otp_code,
    )


@router.post("/register/verify", response_model=UserResponse)
async def register_verify_otp(
    data: VerifyOtpSchema,
    request: Request,
    db: AsyncSession = Depends(get_db),
    otp_service: OTPService = Depends(get_otp_service),
):
    identity_number = _normalize_identity_number(data.momo_number or data.phone_number)
    _enforce_rate_limit("register_verify", identity_number, request.client.host if request.client else None)
    existing_phone_result = await db.execute(
        select(User).filter((User.phone_number == identity_number) | (User.momo_number == identity_number))
    )
    user = existing_phone_result.scalars().first()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Registration not initiated for this number.")

    expires_at = _to_aware(user.otp_expires_at)
    if not expires_at or _now_utc() > expires_at:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "OTP expired. Request a new OTP.")

    identity = user.momo_number or user.phone_number
    if not identity or not await otp_service.verify_otp(identity, data.otp_code):
        user.otp_attempt_count = int(user.otp_attempt_count or 0) + 1
        db.add(user)
        await db.commit()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid OTP.")

    user.is_verified = True
    user.verification_token = None
    user.otp_expires_at = None
    user.otp_attempt_count = 0
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/register")
async def register_user(
    data: RegisterSchema,
    request: Request,
    db: AsyncSession = Depends(get_db),
    otp_service: OTPService = Depends(get_otp_service),
):
    identity_number = _normalize_identity_number(data.momo_number or data.phone_number)
    normalized_email = str(data.email or "").strip().lower() or None
    first_name = _normalize_first_name(data.first_name, data.full_name)
    _enforce_rate_limit("register", identity_number, request.client.host if request.client else None)

    if normalized_email:
        existing_email_result = await db.execute(select(User).filter(func.lower(User.email) == normalized_email))
        existing_email_user = existing_email_result.scalars().first()
        if existing_email_user and existing_email_user.momo_number != identity_number:
            raise HTTPException(status_code=400, detail="Email already registered")

    existing_result = await db.execute(
        select(User).filter((User.phone_number == identity_number) | (User.momo_number == identity_number))
    )
    existing_user = existing_result.scalars().first()

    otp_expires = _now_utc() + timedelta(minutes=2)
    pin_hashed = hash_pin(data.pin)
    status_value = "registered"

    if existing_user:
        if existing_user.is_verified:
            raise HTTPException(status_code=400, detail="Number already registered")

        existing_user.full_name = first_name
        existing_user.email = normalized_email
        existing_user.phone_number = identity_number
        existing_user.momo_number = identity_number
        existing_user.provider = detect_network(identity_number)
        existing_user.pin_hash = pin_hashed
        existing_user.password_hash = pin_hashed
        existing_user.is_agent = bool(data.is_agent)
        existing_user.bound_device_id = data.device_id or existing_user.bound_device_id
        existing_user.first_login_fingerprint = data.device_fingerprint or existing_user.first_login_fingerprint
        existing_user.verification_token = "redis"
        existing_user.otp_expires_at = otp_expires
        existing_user.otp_attempt_count = 0
        existing_user.is_verified = False
        existing_user.kyc_tier = existing_user.kyc_tier or 1
        existing_user.daily_limit = resolve_daily_limit_for_tier(existing_user.kyc_tier)
        ensure_daily_window(existing_user)
        db.add(existing_user)
        status_value = "verify_required"
    else:
        role = "agent" if data.is_agent else "user"
        account_status = "pending_kyc" if data.is_agent else "active"
        new_user = User(
            momo_number=identity_number,
            email=normalized_email,
            phone_number=identity_number,
            full_name=first_name,
            provider=detect_network(identity_number),
            pin_hash=pin_hashed,
            password_hash=pin_hashed,
            is_agent=bool(data.is_agent),
            role=role,
            status=account_status,
            is_verified=False,
            bound_device_id=data.device_id,
            first_login_fingerprint=data.device_fingerprint,
            verification_token="redis",
            otp_expires_at=otp_expires,
            otp_attempt_count=0,
            kyc_tier=1,
            daily_limit=resolve_daily_limit_for_tier(1),
        )
        db.add(new_user)
        await db.flush()
        wallet = Wallet(user_id=new_user.id, currency="GHS", balance=0.0)
        db.add(wallet)
        if data.is_agent:
            if not data.business_name or not data.ghana_card_id or not data.agent_location:
                raise HTTPException(
                    status_code=400,
                    detail="Agent registration requires business_name, ghana_card_id, and agent_location",
                )
            agent = Agent(
                user_id=new_user.id,
                status="pending",
                business_name=data.business_name,
                ghana_card_id=data.ghana_card_id,
                agent_location=data.agent_location,
            )
            db.add(agent)

    otp_code, send_result = await otp_service.issue_otp(identity_number, purpose="access_verify")
    _raise_if_otp_dispatch_failed(send_result)
    await db.commit()

    return _with_debug_otp(
        {
            "status": status_value,
            "message": "Registration successful. Verify OTP.",
            "first_name": first_name,
            "network": detect_network(identity_number),
        },
        otp_service,
        otp_code,
    )


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginSchema, request: Request, db: AsyncSession = Depends(get_db)):
    identity_number = _normalize_identity_number(data.momo_number or data.phone_number)
    _enforce_rate_limit("login", identity_number, request.client.host if request.client else None)
    user_result = await db.execute(
        select(User).filter((User.phone_number == identity_number) | (User.momo_number == identity_number))
    )
    user = user_result.scalars().first()

    if not user:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid credentials")

    locked_until = _to_aware(user.pin_locked_until)
    if locked_until and _now_utc() < locked_until:
        raise HTTPException(
            status.HTTP_423_LOCKED,
            f"Account locked due to failed PIN attempts. Try again after {locked_until.isoformat()}",
        )

    provided_pin = (data.pin or data.password or "").strip()
    if len(provided_pin) != 4 or not provided_pin.isdigit():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "PIN must be 4 digits")

    pin_store = user.pin_hash or user.password_hash
    if not pin_store or not verify_pin(provided_pin, pin_store):
        user.failed_pin_attempts = int(user.failed_pin_attempts or 0) + 1
        if user.failed_pin_attempts >= _PIN_MAX_ATTEMPTS:
            user.pin_locked_until = _now_utc() + timedelta(minutes=_PIN_LOCK_MINUTES)
            logger.warning(
                "Account temporarily locked after failed PIN attempts for %s", user.momo_number or user.phone_number
            )
        db.add(user)
        await db.commit()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid PIN")

    if not user.is_verified:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account not verified. Complete OTP verification.")

    # Device binding: first device binds account, subsequent logins require same device.
    device_id = _normalize_device_id(data.device_id) or "legacy-client"
    fingerprint = data.device_fingerprint or request.headers.get("User-Agent", "")

    if user.bound_device_id and user.bound_device_id != device_id:
        logger.warning(
            "Device rebind during login for %s: %s -> %s",
            user.momo_number or user.phone_number,
            user.bound_device_id,
            device_id,
        )
        user.bound_device_id = device_id
    if not user.bound_device_id:
        user.bound_device_id = device_id
    if user.first_login_fingerprint and fingerprint and user.first_login_fingerprint != fingerprint:
        logger.warning(
            "Fingerprint updated during login for %s",
            user.momo_number or user.phone_number,
        )
        user.first_login_fingerprint = fingerprint
    if not user.first_login_fingerprint and fingerprint:
        user.first_login_fingerprint = fingerprint

    if user.is_agent:
        agent_result = await db.execute(select(Agent).filter(Agent.user_id == user.id))
        agent = agent_result.scalars().first()
        if not agent or str(agent.status).lower() != "active":
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Agent account pending admin approval.",
            )

    user.failed_pin_attempts = 0
    user.pin_locked_until = None
    ensure_daily_window(user)
    if not user.daily_limit:
        user.daily_limit = resolve_daily_limit_for_tier(user.kyc_tier or 1)
    user.last_login_device_id = device_id
    user.last_login_ip = request.client.host if request.client else None
    db.add(user)
    await db.commit()

    access_token = create_jwt(user.id, token_version=int(user.token_version or 0))

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }


@router.post("/access")
async def access_account(
    data: AccessSchema,
    request: Request,
    db: AsyncSession = Depends(get_db),
    otp_service: OTPService = Depends(get_otp_service),
):
    identity = _normalize_identity_number(data.momo_number)
    normalized_email = None
    await _cleanup_stale_unverified(db, identity)
    _enforce_access_rate_limit(identity, request.client.host if request.client else None)

    result = await db.execute(select(User).filter(User.momo_number == identity))
    user = result.scalars().first()

    # Existing user -> login path.
    if user:
        locked_until = _to_aware(user.pin_locked_until)
        if locked_until and _now_utc() < locked_until:
            raise HTTPException(status.HTTP_423_LOCKED, "Account temporarily locked. Try later.")

        pin_store = user.pin_hash or user.password_hash
        if not pin_store or not verify_pin(data.pin, pin_store):
            user.failed_pin_attempts = int(user.failed_pin_attempts or 0) + 1
            if user.failed_pin_attempts >= _PIN_MAX_ATTEMPTS:
                user.pin_locked_until = _now_utc() + timedelta(minutes=_PIN_LOCK_MINUTES)
                logger.warning("PIN lock triggered for %s from IP=%s", identity, request.client.host if request.client else None)
            db.add(user)
            await db.commit()
            raise HTTPException(400, "Invalid PIN")

        # Device binding and fingerprint checks.
        incoming_device_id = _normalize_device_id(data.device_id)
        if user.bound_device_id and incoming_device_id and user.bound_device_id != incoming_device_id:
            logger.warning(
                "Device rebind via access for %s: %s -> %s",
                identity,
                user.bound_device_id,
                incoming_device_id,
            )
            user.bound_device_id = incoming_device_id
        if not user.bound_device_id and incoming_device_id:
            user.bound_device_id = incoming_device_id

        incoming_fingerprint = str(data.device_fingerprint or "").strip()
        if user.first_login_fingerprint and incoming_fingerprint and user.first_login_fingerprint != incoming_fingerprint:
            logger.warning("Fingerprint updated via access for %s", identity)
            user.first_login_fingerprint = incoming_fingerprint
        if not user.first_login_fingerprint and incoming_fingerprint:
            user.first_login_fingerprint = incoming_fingerprint

        if not user.is_verified:
            otp_code, send_result = await otp_service.issue_otp(
                user.momo_number,
                purpose="access_verify",
            )
            _raise_if_otp_dispatch_failed(send_result)
            user.otp_expires_at = _now_utc() + timedelta(minutes=2)
            user.last_login_ip = request.client.host if request.client else None
            db.add(user)
            await db.commit()
            return _with_debug_otp(
                {
                    "status": "verify_required",
                    "first_name": _safe_first_name_from_user(user),
                    "network": detect_network(identity),
                },
                otp_service,
                otp_code,
            )

        if user.is_agent and str(user.status or "").lower() in {"pending_kyc", "pending", "pending_kyc_review"}:
            return {
                "status": "pending_kyc",
                "first_name": _safe_first_name_from_user(user),
                "network": detect_network(identity),
            }

        user.failed_pin_attempts = 0
        user.pin_locked_until = None
        user.last_login_ip = request.client.host if request.client else None
        if data.device_id:
            user.last_login_device_id = data.device_id
        db.add(user)
        await db.commit()
        token = create_jwt(user.id, token_version=int(user.token_version or 0))
        return {
            "status": "login_success",
            "access_token": token,
            "first_name": _safe_first_name_from_user(user),
            "network": detect_network(identity),
        }

    # New user -> auto registration path.
    if len(data.pin) != 4 or not data.pin.isdigit():
        raise HTTPException(400, "PIN must be 4 digits")

    first_name = _normalize_first_name(data.first_name)
    pin_hashed = hash_pin(data.pin)
    role = "agent" if data.is_agent else "user"
    account_status = "pending_kyc" if data.is_agent else "active"
    new_user = User(
        momo_number=identity,
        phone_number=identity,
        email=normalized_email,
        full_name=first_name,
        provider=detect_network(identity),
        pin_hash=pin_hashed,
        password_hash=pin_hashed,
        is_agent=bool(data.is_agent),
        role=role,
        status=account_status,
        is_verified=False,
        bound_device_id=data.device_id,
        first_login_fingerprint=data.device_fingerprint,
        kyc_tier=1,
        daily_limit=resolve_daily_limit_for_tier(1),
    )
    db.add(new_user)
    await db.flush()
    wallet = Wallet(user_id=new_user.id, currency="GHS", balance=0.0)
    db.add(wallet)
    otp_code, send_result = await otp_service.issue_otp(
        identity,
        purpose="access_verify",
    )
    _raise_if_otp_dispatch_failed(send_result)
    new_user.otp_expires_at = _now_utc() + timedelta(minutes=2)
    new_user.last_login_ip = request.client.host if request.client else None
    db.add(new_user)
    await db.commit()
    return _with_debug_otp(
        {
            "status": "registered",
            "message": "OTP sent. Verify to continue.",
            "first_name": first_name,
            "network": detect_network(identity),
        },
        otp_service,
        otp_code,
    )


@router.post("/lookup-name", response_model=LookupNameResponse)
async def lookup_name_by_number(
    data: LookupNameSchema,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Lookup display name for a registered mobile money number.
    Used by clients to auto-fill the user's first name during auth/register flows.
    """
    identity = _normalize_identity_number(data.momo_number)
    _enforce_rate_limit("lookup_name", identity, request.client.host if request.client else None)

    result = await db.execute(
        select(User).filter((User.phone_number == identity) | (User.momo_number == identity))
    )
    user = result.scalars().first()

    network = detect_network(identity)
    network_label = network if network != "UNKNOWN" else "UNKNOWN"
    network_pretty = {
        "MTN": "MTN",
        "TELECEL": "Telecel",
        "AIRTELTIGO": "AirtelTigo",
    }.get(network, network.title() if network != "UNKNOWN" else "Unknown")

    if not user:
        fallback_display = "Customer"
        if network != "UNKNOWN":
            fallback_display = f"{network_pretty} User"
        return LookupNameResponse(
            registered=False,
            momo_number=identity,
            network=network_label,
            first_name="",
            full_name="",
            display_name=fallback_display,
            is_verified=False,
        )

    first_name = _safe_first_name_from_user(user)
    full_name = str(user.full_name or "").strip()
    display_name = first_name or full_name or "Customer"
    return LookupNameResponse(
        registered=True,
        momo_number=identity,
        network=network_label,
        first_name=first_name,
        full_name=full_name,
        display_name=display_name,
        is_verified=bool(user.is_verified),
    )


@router.post("/verify")
async def verify_account(
    data: VerifySchema,
    request: Request,
    db: AsyncSession = Depends(get_db),
    otp_service: OTPService = Depends(get_otp_service),
):
    identity = _normalize_identity_number(data.momo_number)
    result = await db.execute(select(User).filter(User.momo_number == identity))
    user = result.scalars().first()
    if not user:
        raise HTTPException(404, "Account not found")

    ok = await otp_service.verify_otp(identity, data.otp, purpose="access_verify")
    if not ok:
        raise HTTPException(400, "Invalid OTP")

    user.is_verified = True
    user.otp_expires_at = None
    user.last_login_ip = request.client.host if request.client else None
    db.add(user)
    await db.commit()
    token = create_jwt(user.id, token_version=int(user.token_version or 0))
    return {
        "status": "verified",
        "access_token": token,
        "first_name": _safe_first_name_from_user(user),
        "network": detect_network(identity),
    }


@router.post("/resend-otp")
async def resend(data: ResendSchema, db: AsyncSession = Depends(get_db), otp_service: OTPService = Depends(get_otp_service)):
    identity = _normalize_identity_number(data.momo_number)
    result = await db.execute(select(User).filter(User.momo_number == identity))
    user = result.scalars().first()
    if not user:
        raise HTTPException(404, "Account not found")

    otp_code, send_result = await otp_service.resend_otp(
        user.momo_number,
        purpose="access_verify",
    )
    _raise_if_otp_dispatch_failed(send_result)
    user.otp_expires_at = _now_utc() + timedelta(minutes=2)
    db.add(user)
    await db.commit()
    return _with_debug_otp({"message": "OTP resent"}, otp_service, otp_code)


@router.post("/change-pin")
async def change_pin(
    data: ChangePinSchema,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    otp_service: OTPService = Depends(get_otp_service),
):
    result = await db.execute(select(User).filter(User.id == current_user.id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not verify_pin(data.old_pin, user.pin_hash or user.password_hash or ""):
        raise HTTPException(status_code=400, detail="Incorrect old PIN")

    if len(data.new_pin) != 4 or not data.new_pin.isdigit():
        raise HTTPException(status_code=400, detail="PIN must be 4 digits")

    pin_hashed = hash_pin(data.new_pin)
    user.pin_hash = pin_hashed
    user.password_hash = pin_hashed
    user.last_login_ip = request.client.host if request.client else None
    if data.device_fingerprint:
        user.first_login_fingerprint = data.device_fingerprint
    revoke_user_tokens(user)
    db.add(user)
    await db.commit()

    target = user.momo_number or user.phone_number
    if target:
        otp_service.send_sms(target, "Your PIN was changed")
    return {"message": "PIN updated successfully"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).filter(User.id == current_user.id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("/logout")
async def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).filter(User.id == current_user.id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Server-side sign-out revokes currently issued JWTs.
    revoke_user_tokens(user)
    user.last_login_ip = request.client.host if request.client else None
    db.add(user)
    await db.commit()

    return {"message": "Signed out successfully. Account remains active. Please sign in again."}


@router.post("/reset-pin/request-otp")
async def request_reset_pin_otp(
    data: ResetPinRequestSchema,
    request: Request,
    db: AsyncSession = Depends(get_db),
    otp_service: OTPService = Depends(get_otp_service),
):
    identity = _normalize_identity_number(data.momo_number)
    _enforce_rate_limit("reset_pin_request", identity, request.client.host if request.client else None)
    result = await db.execute(select(User).filter((User.momo_number == identity) | (User.phone_number == identity)))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="Account not found")
    otp_code, send_result = await otp_service.issue_otp(identity, purpose="reset_pin")
    _raise_if_otp_dispatch_failed(send_result)
    return _with_debug_otp({"message": "OTP sent."}, otp_service, otp_code)


@router.post("/reset-pin")
async def reset_pin(
    data: ResetPinSchema,
    request: Request,
    db: AsyncSession = Depends(get_db),
    otp_service: OTPService = Depends(get_otp_service),
):
    identity = _normalize_identity_number(data.momo_number)
    _enforce_rate_limit("reset_pin", identity, request.client.host if request.client else None)
    result = await db.execute(select(User).filter((User.momo_number == identity) | (User.phone_number == identity)))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="Account not found")

    if not await otp_service.verify_otp(identity, data.otp, purpose="reset_pin"):
        raise HTTPException(status_code=400, detail="Invalid OTP")

    pin_hashed = hash_pin(data.new_pin)
    user.pin_hash = pin_hashed
    user.password_hash = pin_hashed
    user.failed_pin_attempts = 0
    user.pin_locked_until = None
    user.last_login_ip = request.client.host if request.client else None
    if data.device_fingerprint:
        user.first_login_fingerprint = data.device_fingerprint
    revoke_user_tokens(user)
    db.add(user)
    await db.commit()

    otp_service.send_sms(identity, "Your PIN was reset")
    return {"message": "PIN reset successful"}

@router.post("/reset")
async def reset_password(token: str, new_password: str, db: AsyncSession = Depends(get_db)):

    user_result = await db.execute(select(User).filter(User.reset_token == token))
    user = user_result.scalars().first()

    if not user:
        raise HTTPException(400, "Invalid token")

    user.password_hash = hash_password(new_password)
    user.reset_token = None
    await db.commit()

    return {"message": "Password reset successful"}
