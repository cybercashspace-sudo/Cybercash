from __future__ import annotations

import asyncio
import os
import sys
from typing import Generator

import pytest
from fastapi.testclient import TestClient

# Ensure project root is importable when tests are run directly.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
os.environ.setdefault("RUNNING_TESTS", "true")
os.environ.setdefault("OTP_PROVIDER", "log")
os.environ.setdefault("SMS_PROVIDER", "log")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_cybercash.db")
os.environ.setdefault("SYNC_DATABASE_URL", "sqlite:///./test_cybercash.db")
os.environ.setdefault("FLUTTERWAVE_SECRET_KEY", "test_flutterwave_secret")
os.environ.setdefault("FLUTTERWAVE_WEBHOOK_HASH", "test_flutterwave_webhook_hash")
os.environ.setdefault("FLW_CLIENT_ID", "test_flw_client_id")
os.environ.setdefault("FLW_CLIENT_SECRET", "test_flw_client_secret")
os.environ.setdefault("FLW_ENCRYPTION_KEY", "MDEyMzQ1Njc4OWFiY2RlZg==")

# Ensure all model tables are registered on Base.metadata before create_all.
import backend.models.user
import backend.models.wallet
import backend.models.virtualcard
import backend.models.agent
import backend.models.transaction
import backend.models.payment
import backend.models.cryptowallet
import backend.models.cryptotransaction
import backend.models.account
import backend.models.journalentry
import backend.models.ledgerentry
import backend.models.loan
import backend.models.loan_application
import backend.models.agent_risk_profile
import backend.models.risk_event
import backend.models.bundle_catalog
import backend.models.commission
import backend.models.data_order

from backend.main import app
from backend.database import Base, engine, SessionLocal, async_session
from backend.models import User
from backend.core.security import create_access_token
from backend.services.ledger_service import LedgerService
from backend.services.momo import MomoService
from backend.services.crypto import CryptoService
from backend.services.bank import BankService
from backend.services.flutterwave_service import FlutterwaveService


@pytest.fixture(scope="session", autouse=True)
def test_database_lifecycle() -> Generator[None, None, None]:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    os.environ["RUNNING_TESTS"] = "true"

@pytest.fixture(autouse=True)
def isolate_test_data():
    db = SessionLocal()
    try:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(table.delete())
        db.commit()
        yield
    finally:
        db.close()


@pytest.fixture(autouse=True)
def seed_standard_ledger_accounts(isolate_test_data):
    async def _seed() -> None:
        async with async_session() as session:
            ledger_service = LedgerService(session)
            await ledger_service._initialize_standard_accounts()

    asyncio.run(_seed())
    yield


@pytest.fixture(autouse=True)
def deterministic_external_services(monkeypatch: pytest.MonkeyPatch):
    async def fake_momo_withdrawal(*args, **kwargs):
        return {
            "status": "pending",
            "message": "Simulated Momo initiation.",
            "processor_transaction_id": "MOMO_TEST_ID",
        }

    async def fake_crypto_withdrawal(*args, **kwargs):
        return {
            "status": "awaiting_confirmation",
            "message": "Simulated Crypto initiation.",
            "transaction_hash": "CRYPTO_TEST_HASH",
        }

    async def fake_bank_withdrawal(*args, **kwargs):
        return {
            "status": "pending",
            "message": "Simulated Bank initiation.",
            "processor_transaction_id": "BANK_TEST_ID",
        }

    async def fake_flutterwave_transfer(*args, **kwargs):
        payload = kwargs.get("meta") or {}
        return {
            "status": "success",
            "message": "Simulated Flutterwave transfer.",
            "data": {
                "id": "FLW_TEST_ID",
                "reference": kwargs.get("reference") or "FLW_REF_TEST",
                "status": "NEW",
                "account_bank": kwargs.get("network") or "MTN",
                "account_number": kwargs.get("account_number"),
                "meta": payload,
            },
            "transfer_status": "NEW",
        }

    monkeypatch.setattr(MomoService, "initiate_withdrawal", fake_momo_withdrawal, raising=True)
    monkeypatch.setattr(CryptoService, "initiate_withdrawal", fake_crypto_withdrawal, raising=True)
    monkeypatch.setattr(BankService, "initiate_withdrawal", fake_bank_withdrawal, raising=True)
    monkeypatch.setattr(FlutterwaveService, "initiate_transfer", fake_flutterwave_transfer, raising=True)


@pytest.fixture(name="db_session")
def db_session_fixture():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(name="client")
def client_fixture():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def admin_user(db_session):
    user = User(
        email="admin@example.com",
        password_hash="hashedpassword",
        is_admin=True,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_auth_headers(admin_user: User):
    access_token = create_access_token(data={"sub": admin_user.email})
    return {"Authorization": f"Bearer {access_token}"}
