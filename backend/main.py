import os
import logging
from dotenv import load_dotenv

_backend_dir = os.path.dirname(os.path.abspath(__file__))
_root_dir = os.path.dirname(_backend_dir)

# Load shared values first, then let backend/.env win for backend credentials.
root_dotenv_path = os.path.join(_root_dir, ".env")
backend_dotenv_path = os.path.join(_backend_dir, ".env")
load_dotenv(root_dotenv_path)
load_dotenv(backend_dotenv_path, override=True)

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text, select, or_

from backend.database import async_engine, async_session, Base
from backend.models import User, Agent, Wallet
from utils.security import hash_pin
from utils.network import detect_network
from backend.routes import (
    auth,
    wallet,
    virtualcards,
    admin,
    binance_admin,
    agents,
    agent_transactions,
    payments,
    crypto,
    paystack,
    ledger,
    ussd,
    loans,
    transactions,
    bundles,
    airtime,
    sms,
    payouts,
    settings_routes,
    data_orders,
    otp,
)

# ==========================================
# FASTAPI INIT
# ==========================================

app = FastAPI(title="CyberCash ULTRA PRO Backend")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@app.get("/health")
async def healthcheck():
    return {"status": "ok", "service": "cybercash-backend"}

def _mask_secret(value: str, prefix: int = 3, suffix: int = 2) -> str:
    raw = str(value or "")
    if not raw:
        return "<missing>"
    if len(raw) <= (prefix + suffix):
        return "***"
    return f"{raw[:prefix]}***{raw[-suffix:]}"


def _patch_datetime_type() -> str:
    dialect_name = ""
    try:
        dialect_name = str(getattr(getattr(async_engine, "dialect", None), "name", "") or "").strip().lower()
    except Exception:
        dialect_name = ""
    return "TIMESTAMP" if dialect_name == "postgresql" else "DATETIME"

# ==========================================
# DATABASE SCHEMA PATCH SYSTEM
# ==========================================

def _apply_schema_patches(sync_conn) -> None:
    inspector = inspect(sync_conn)
    datetime_type = _patch_datetime_type()

    # -------- TRANSACTIONS PATCH --------
    if "transactions" in inspector.get_table_names():
        tx_cols = {c["name"] for c in inspector.get_columns("transactions")}
        if "metadata_json" not in tx_cols:
            sync_conn.execute(
                text("ALTER TABLE transactions ADD COLUMN metadata_json VARCHAR")
            )

    # -------- USERS PATCH --------
    if "users" in inspector.get_table_names():
        user_cols = {c["name"] for c in inspector.get_columns("users")}

        patches = {
            "momo_number": "VARCHAR(15)",
            "provider": "VARCHAR",
            "pin_hash": "VARCHAR",
            "role": "VARCHAR DEFAULT 'user'",
            "status": "VARCHAR DEFAULT 'active'",
            "otp_expires_at": datetime_type,
            "otp_attempt_count": "INTEGER DEFAULT 0",
            "bound_device_id": "VARCHAR",
            "first_login_fingerprint": "VARCHAR",
            "last_login_device_id": "VARCHAR",
            "last_login_ip": "VARCHAR",
            "failed_pin_attempts": "INTEGER DEFAULT 0",
            "pin_locked_until": datetime_type,
            "kyc_tier": "INTEGER DEFAULT 1",
            "daily_limit": "FLOAT DEFAULT 2000.0",
            "daily_spent": "FLOAT DEFAULT 0.0",
            "daily_spent_reset_at": datetime_type,
            "token_version": "INTEGER DEFAULT 0",
        }

        for column, definition in patches.items():
            if column not in user_cols:
                sync_conn.execute(
                    text(f"ALTER TABLE users ADD COLUMN {column} {definition}")
                )

    # -------- LOAN APPLICATIONS PATCH --------
    if "loan_applications" in inspector.get_table_names():
        application_cols = {c["name"] for c in inspector.get_columns("loan_applications")}
        application_patches = {
            "user_id": "INTEGER",
        }
        for column, definition in application_patches.items():
            if column not in application_cols:
                sync_conn.execute(
                    text(f"ALTER TABLE loan_applications ADD COLUMN {column} {definition}")
                )

    # -------- LOANS PATCH --------
    if "loans" in inspector.get_table_names():
        loan_cols = {c["name"] for c in inspector.get_columns("loans")}
        loan_patches = {
            "user_id": "INTEGER",
            "repayment_duration": "INTEGER",
            "base_fee_percentage": "FLOAT DEFAULT 0.0",
            "base_fee_amount": "FLOAT DEFAULT 0.0",
            "late_fee_percentage": "FLOAT DEFAULT 0.0",
            "late_fee_amount": "FLOAT DEFAULT 0.0",
            "late_fee_applied_at": datetime_type,
        }
        for column, definition in loan_patches.items():
            if column not in loan_cols:
                sync_conn.execute(
                    text(f"ALTER TABLE loans ADD COLUMN {column} {definition}")
                )


async def _ensure_default_access_user() -> None:
    """
    Ensure a default admin/agent/user account exists for local dashboards.
    """
    default_phone = "0247689184"
    default_pin = "2139"

    async with async_session() as session:
        result = await session.execute(
            select(User).filter(
                or_(
                    User.momo_number == default_phone,
                    User.phone_number == default_phone,
                )
            )
        )
        user = result.scalars().first()
        pin_hashed = hash_pin(default_pin)

        if not user:
            user = User(
                momo_number=default_phone,
                phone_number=default_phone,
                full_name="Default Admin",
                provider=detect_network(default_phone),
                pin_hash=pin_hashed,
                password_hash=pin_hashed,
                is_active=True,
                is_admin=True,
                is_agent=True,
                is_verified=True,
                status="active",
                role="admin",
                failed_pin_attempts=0,
                pin_locked_until=None,
            )
            session.add(user)
            await session.flush()
        else:
            user.momo_number = default_phone
            user.phone_number = default_phone
            user.provider = detect_network(default_phone)
            user.pin_hash = pin_hashed
            user.password_hash = pin_hashed
            user.is_active = True
            user.is_admin = True
            user.is_agent = True
            user.is_verified = True
            user.status = "active"
            user.role = "admin"
            user.failed_pin_attempts = 0
            user.pin_locked_until = None
            session.add(user)

        result = await session.execute(select(Wallet).filter(Wallet.user_id == user.id))
        wallet = result.scalars().first()
        if not wallet:
            wallet = Wallet(user_id=user.id, balance=0.0, currency="GHS")
            session.add(wallet)

        result = await session.execute(select(Agent).filter(Agent.user_id == user.id))
        agent = result.scalars().first()
        if not agent:
            agent = Agent(
                user_id=user.id,
                status="active",
                business_name="Default Admin Agent",
                agent_location="HQ",
                commission_rate=0.02,
                float_balance=0.0,
                commission_balance=0.0,
            )
            session.add(agent)
        else:
            agent.status = "active"
            if agent.commission_rate is None:
                agent.commission_rate = 0.02
            session.add(agent)

        await session.commit()

# ==========================================
# STARTUP EVENT
# ==========================================

@app.on_event("startup")
async def startup_db_events():
    from backend.services.otp_service import get_otp_service
    from backend.services.sms_service import get_sms_service

    configured_otp_provider = str(os.getenv("OTP_PROVIDER", "log") or "log").strip().lower()
    configured_sms_provider = str(os.getenv("SMS_PROVIDER", "") or "").strip().lower() or configured_otp_provider
    configured_sender_id = (
        str(os.getenv("SMS_SENDER_ID", "") or os.getenv("MNOTIFY_SENDER", "") or "CyberCash").strip() or "CyberCash"
    )
    otp_provider = get_otp_service().provider
    sms_service = get_sms_service()
    sms_provider = sms_service.provider
    logger.info(
        "OTP/SMS config loaded: OTP_PROVIDER=%s (effective=%s) SMS_PROVIDER=%s (effective=%s) SMS_SENDER_ID=%s (effective=%s) MNOTIFY_API_KEY=%s MNOTIFY_SENDER=%s",
        configured_otp_provider,
        otp_provider,
        configured_sms_provider,
        sms_provider,
        configured_sender_id,
        sms_service.sender_id,
        _mask_secret(os.getenv("MNOTIFY_API_KEY", "")),
        str(os.getenv("MNOTIFY_SENDER", "") or "").strip() or "<default>",
    )

    if os.environ.get("RUNNING_TESTS") != "true":
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.run_sync(_apply_schema_patches)

        await _ensure_default_access_user()

    from backend.services.ledger_service import LedgerService

    async with async_session() as seed_db:
        ledger_service = LedgerService(seed_db)
        await ledger_service._initialize_standard_accounts()
        await seed_db.commit()

    logger.info("✅ Database initialized successfully")

# ==========================================
# CORS CONFIG
# ==========================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# ROUTERS
# ==========================================

app.include_router(auth.router)
app.include_router(wallet.router)
app.include_router(virtualcards.router)
app.include_router(admin.router)
app.include_router(binance_admin.router)
app.include_router(agents.router)
app.include_router(agent_transactions.router)
app.include_router(payments.router)
app.include_router(crypto.router)
app.include_router(paystack.router)
app.include_router(ledger.router)
app.include_router(ussd.router)
app.include_router(loans.router)
app.include_router(transactions.router)
app.include_router(bundles.router)
app.include_router(airtime.router)
app.include_router(data_orders.router)
app.include_router(sms.router)
app.include_router(payouts.router)
app.include_router(settings_routes.router)
app.include_router(otp.router)

# ==========================================
# ADMIN DASHBOARD ENDPOINT
# ==========================================

@app.get("/transactions")
async def admin_get_transactions():
    """
    Lightweight endpoint for Kivy Admin Dashboard.
    Returns minimal transaction data to avoid ORM complexity.
    """
    from backend.models import Transaction

    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="This legacy endpoint has been removed. Use /admin/transactions instead.",
    )

    return [
        {
            "id": row.id,
            "user_id": row.user_id,
            "amount": float(row.amount),
            "status": row.status,
        }
        for row in rows
    ]

# ==========================================
# ROOT
# ==========================================

@app.get("/")
def root():
    return {"message": "CyberCash ULTRA PRO API running 🚀"}
