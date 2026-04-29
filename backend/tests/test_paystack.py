from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from backend.database import engine, async_engine
from backend.main import app
from backend.dependencies.auth import get_current_user
from backend.models import User, Wallet, Transaction, JournalEntry, LedgerEntry
from backend.core.config import settings
from backend.core.transaction_types import TransactionType
from backend.services.paystack_service import PaystackService
from unittest.mock import patch, AsyncMock
import pytest
import httpx
import hmac
import hashlib
import json


@pytest.fixture(scope="module")
def test_db():
    db = Session(bind=engine)
    yield db
    db.close()


def override_get_current_user_paystack():
    return User(
        id=100,
        email="paystack_test@example.com",
        full_name="Paystack Test User",
        is_active=True,
        is_verified=True,
    )


@pytest.fixture(autouse=True)
def auth_override_paystack():
    app.dependency_overrides[get_current_user] = override_get_current_user_paystack
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client
    try:
        async_engine.sync_engine.dispose()
    except Exception:
        pass


@pytest.fixture(autouse=True)
def setup_paystack_test_user_and_wallet(test_db: Session):
    test_db.query(Transaction).delete()
    test_db.query(Wallet).delete()
    test_db.query(User).delete()
    test_db.commit()

    user = User(
        id=100,
        email="paystack_test@example.com",
        full_name="Paystack Test User",
        password_hash="hashed_password",
        is_active=True,
        is_verified=True,
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)

    wallet = Wallet(user_id=user.id, currency="GHS", balance=0.0)
    test_db.add(wallet)
    test_db.commit()
    test_db.refresh(wallet)
    yield


def test_initiate_paystack_payment_success(test_db: Session, client: TestClient):
    with patch.object(
        PaystackService,
        "initiate_payment",
        new=AsyncMock(
            return_value={
                "authorization_url": "https://paystack.com/pay/testref",
                "access_code": "test_access_code",
                "reference": "test_ref",
            }
        ),
    ):
        response = client.post("/paystack/initiate", json={"amount": 100.0})

    assert response.status_code == 200
    data = response.json()
    assert data["authorization_url"] == "https://paystack.com/pay/testref"
    assert data["reference"] == "test_ref"

    transaction = test_db.query(Transaction).filter(Transaction.provider_reference == "test_ref").first()
    assert transaction is not None
    assert transaction.status == "pending"
    assert transaction.amount == 100.0
    assert transaction.type == TransactionType.FUNDING
    assert transaction.provider == "paystack"


def test_initiate_paystack_payment_negative_amount(test_db: Session, client: TestClient):
    response = client.post("/paystack/initiate", json={"amount": -10.0})
    assert response.status_code == 400
    assert "at least GHS 1.00" in response.json()["detail"]


def test_initiate_paystack_payment_auth_failure_maps_to_gateway_error(client: TestClient, monkeypatch):
    from backend.services import paystack_service as paystack_module

    monkeypatch.setattr(paystack_module.settings, "PAYSTACK_SECRET_KEY", "sk_test_fake", raising=False)

    class FakeResponse:
        status_code = 401
        text = '{"message":"Unauthorized"}'

        def json(self):
            return {"message": "Unauthorized"}

        def raise_for_status(self):
            request = httpx.Request("POST", "https://api.paystack.co/transaction/initialize")
            raise httpx.HTTPStatusError("Unauthorized", request=request, response=self)

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(paystack_module.httpx, "AsyncClient", FakeAsyncClient, raising=True)

    response = client.post("/paystack/initiate", json={"amount": 100.0})
    assert response.status_code == 502
    assert "Paystack authentication failed" in response.json()["detail"]


def test_paystack_secret_key_normalization_strips_bearer_prefix():
    from backend.services.paystack_service import normalize_paystack_secret_key

    assert normalize_paystack_secret_key('  Bearer  sk_test_123456  ') == "sk_test_123456"


def test_paystack_signature_helper_accepts_any_valid_candidate():
    from backend.services.paystack_service import (
        compute_paystack_signature,
        is_valid_paystack_signature,
    )

    body = b'{"event":"charge.success","data":{"reference":"sig_ref"}}'
    signature = compute_paystack_signature("sk_test_secondary", body)

    assert is_valid_paystack_signature(signature, body, ["sk_test_primary", "sk_test_secondary"])
    assert not is_valid_paystack_signature("bad_signature", body, ["sk_test_primary", "sk_test_secondary"])


def test_verify_paystack_payment_success(test_db: Session, client: TestClient):
    user = test_db.query(User).filter(User.email == "paystack_test@example.com").first()
    wallet = test_db.query(Wallet).filter(Wallet.user_id == user.id).first()

    pending_transaction = Transaction(
        user_id=user.id,
        wallet_id=wallet.id,
        type=TransactionType.FUNDING,
        amount=50.0,
        currency="GHS",
        status="pending",
        provider="paystack",
        provider_reference="verify_ref",
    )
    test_db.add(pending_transaction)
    test_db.commit()

    with patch.object(
        PaystackService,
        "verify_payment",
        new=AsyncMock(
            return_value={
                "amount": 5000,
                "currency": "GHS",
                "status": "success",
                "reference": "verify_ref",
                "customer": {"email": "paystack_test@example.com"},
            }
        ),
    ):
        response = client.get("/paystack/verify/verify_ref")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "credited" in data["message"].lower()
    assert data["credited_amount"] == 50.0
    assert data["wallet_balance"] == 50.0

    test_db.expire_all()
    updated_wallet = test_db.query(Wallet).filter(Wallet.user_id == user.id).first()
    assert updated_wallet.balance == 50.0

    completed_transaction = test_db.query(Transaction).filter(Transaction.provider_reference == "verify_ref").first()
    assert completed_transaction.status == "completed"

    journal = test_db.query(JournalEntry).filter(JournalEntry.transaction_id == completed_transaction.id).first()
    assert journal is not None
    ledger_rows = test_db.query(LedgerEntry).filter(LedgerEntry.journal_entry_id == journal.id).all()
    assert len(ledger_rows) == 2


def test_verify_paystack_payment_failed(test_db: Session, client: TestClient):
    user = test_db.query(User).filter(User.email == "paystack_test@example.com").first()
    wallet = test_db.query(Wallet).filter(Wallet.user_id == user.id).first()

    pending_transaction = Transaction(
        user_id=user.id,
        wallet_id=wallet.id,
        type=TransactionType.FUNDING,
        amount=50.0,
        currency="GHS",
        status="pending",
        provider="paystack",
        provider_reference="failed_verify_ref",
    )
    test_db.add(pending_transaction)
    test_db.commit()

    with patch.object(
        PaystackService,
        "verify_payment",
        new=AsyncMock(
            return_value={
                "amount": 5000,
                "currency": "GHS",
                "status": "failed",
                "reference": "failed_verify_ref",
                "customer": {"email": "paystack_test@example.com"},
            }
        ),
    ):
        response = client.get("/paystack/verify/failed_verify_ref")

    assert response.status_code == 400
    assert "Payment verification failed: failed" in response.json()["detail"]

    failed_transaction = test_db.query(Transaction).filter(Transaction.provider_reference == "failed_verify_ref").first()
    assert failed_transaction.status == "failed"

    updated_wallet = test_db.query(Wallet).filter(Wallet.user_id == user.id).first()
    assert updated_wallet.balance == 0.0


def test_verify_paystack_payment_abandoned_treated_as_pending_then_webhook_completes(test_db: Session, client: TestClient):
    user = test_db.query(User).filter(User.email == "paystack_test@example.com").first()
    wallet = test_db.query(Wallet).filter(Wallet.user_id == user.id).first()

    pending_transaction = Transaction(
        user_id=user.id,
        wallet_id=wallet.id,
        type=TransactionType.FUNDING,
        amount=40.0,
        currency="GHS",
        status="pending",
        provider="paystack",
        provider_reference="abandoned_ref",
    )
    test_db.add(pending_transaction)
    test_db.commit()

    with patch.object(
        PaystackService,
        "verify_payment",
        new=AsyncMock(
            return_value={
                "amount": 4000,
                "currency": "GHS",
                "status": "abandoned",
                "reference": "abandoned_ref",
                "customer": {"email": "paystack_test@example.com"},
            }
        ),
    ):
        response = client.get("/paystack/verify/abandoned_ref")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pending"
    assert "credited automatically" in data["message"].lower()

    test_db.expire_all()
    unchanged_wallet = test_db.query(Wallet).filter(Wallet.user_id == user.id).first()
    assert unchanged_wallet.balance == 0.0
    tx = test_db.query(Transaction).filter(Transaction.provider_reference == "abandoned_ref").first()
    assert tx is not None
    assert tx.status == "pending"

    webhook_payload = {
        "event": "charge.success",
        "data": {
            "reference": "abandoned_ref",
            "amount": 4000,
            "currency": "GHS",
            "status": "success",
            "customer": {"email": "paystack_test@example.com"},
        },
    }
    body = json.dumps(webhook_payload).encode("utf-8")
    secret = (settings.PAYSTACK_SECRET_KEY or "").encode("utf-8")
    signature = hmac.new(secret, msg=body, digestmod=hashlib.sha512).hexdigest()

    webhook_response = client.post(
        "/paystack/webhook",
        headers={"x-paystack-signature": signature},
        content=body,
    )

    assert webhook_response.status_code == 200

    test_db.expire_all()
    updated_wallet = test_db.query(Wallet).filter(Wallet.user_id == user.id).first()
    assert updated_wallet.balance == 40.0
    completed_transaction = test_db.query(Transaction).filter(Transaction.provider_reference == "abandoned_ref").first()
    assert completed_transaction.status == "completed"


def test_paystack_webhook_charge_success(test_db: Session, client: TestClient):
    user = test_db.query(User).filter(User.email == "paystack_test@example.com").first()
    wallet = test_db.query(Wallet).filter(Wallet.user_id == user.id).first()

    pending_transaction = Transaction(
        user_id=user.id,
        wallet_id=wallet.id,
        type=TransactionType.FUNDING,
        amount=25.0,
        currency="GHS",
        status="pending",
        provider="paystack",
        provider_reference="webhook_ref",
    )
    test_db.add(pending_transaction)
    test_db.commit()

    webhook_payload = {
        "event": "charge.success",
        "data": {
            "reference": "webhook_ref",
            "amount": 2500,
            "currency": "GHS",
            "status": "success",
            "customer": {"email": "paystack_test@example.com"},
        },
    }
    body = json.dumps(webhook_payload).encode("utf-8")
    secret = (settings.PAYSTACK_SECRET_KEY or "").encode("utf-8")
    signature = hmac.new(secret, msg=body, digestmod=hashlib.sha512).hexdigest()

    response = client.post(
        "/paystack/webhook",
        headers={"x-paystack-signature": signature},
        content=body,
    )
    assert response.status_code == 200
    assert "Payment completed and wallet updated." in response.json()["message"]

    test_db.expire_all()
    updated_wallet = test_db.query(Wallet).filter(Wallet.user_id == user.id).first()
    assert updated_wallet.balance == 25.0

    completed_transaction = test_db.query(Transaction).filter(Transaction.provider_reference == "webhook_ref").first()
    assert completed_transaction.status == "completed"


def test_paystack_deposit_idempotent_after_verify_then_webhook(test_db: Session, client: TestClient):
    user = test_db.query(User).filter(User.email == "paystack_test@example.com").first()
    wallet = test_db.query(Wallet).filter(Wallet.user_id == user.id).first()

    pending_transaction = Transaction(
        user_id=user.id,
        wallet_id=wallet.id,
        type=TransactionType.FUNDING,
        amount=30.0,
        currency="GHS",
        status="pending",
        provider="paystack",
        provider_reference="idem_ref",
    )
    test_db.add(pending_transaction)
    test_db.commit()

    with patch.object(
        PaystackService,
        "verify_payment",
        new=AsyncMock(
            return_value={
                "amount": 3000,
                "currency": "GHS",
                "status": "success",
                "reference": "idem_ref",
                "customer": {"email": "paystack_test@example.com"},
            }
        ),
    ):
        verify_response = client.get("/paystack/verify/idem_ref")

    assert verify_response.status_code == 200
    assert verify_response.json()["status"] == "success"

    test_db.expire_all()
    updated_wallet = test_db.query(Wallet).filter(Wallet.user_id == user.id).first()
    assert updated_wallet.balance == 30.0

    webhook_payload = {
        "event": "charge.success",
        "data": {
            "reference": "idem_ref",
            "amount": 3000,
            "currency": "GHS",
            "status": "success",
            "customer": {"email": "paystack_test@example.com"},
        },
    }
    body = json.dumps(webhook_payload).encode("utf-8")
    secret = (settings.PAYSTACK_SECRET_KEY or "").encode("utf-8")
    signature = hmac.new(secret, msg=body, digestmod=hashlib.sha512).hexdigest()

    webhook_response = client.post(
        "/paystack/webhook",
        headers={"x-paystack-signature": signature},
        content=body,
    )

    assert webhook_response.status_code == 200
    assert "already completed" in webhook_response.json()["message"].lower()

    test_db.expire_all()
    updated_wallet = test_db.query(Wallet).filter(Wallet.user_id == user.id).first()
    assert updated_wallet.balance == 30.0


def test_paystack_webhook_invalid_signature(test_db: Session, client: TestClient):
    webhook_payload = {
        "event": "charge.success",
        "data": {
            "reference": "invalid_signature_ref",
            "amount": 1000,
            "currency": "GHS",
            "status": "success",
            "customer": {"email": "paystack_test@example.com"},
        },
    }

    response = client.post(
        "/paystack/webhook",
        headers={"x-paystack-signature": "some_signature"},
        json=webhook_payload,
    )
    assert response.status_code == 400
    assert "Invalid webhook signature." in response.json()["detail"]
