from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from backend.database import engine, async_engine
from backend.main import app
from backend.dependencies.auth import get_current_user
from backend.models import User, Agent, Transaction, Wallet
from backend.core.config import settings
from backend.services.paystack_service import PaystackService
from unittest.mock import patch, AsyncMock
import pytest


@pytest.fixture(scope="module")
def test_db():
    db = Session(bind=engine)
    yield db
    db.close()


def override_get_current_user_agent_reg():
    db = Session(bind=engine)
    try:
        user = db.query(User).filter(User.id == 200).first()
        if user:
            return User(
                id=user.id,
                email=user.email,
                full_name=user.full_name,
                is_active=user.is_active,
                is_verified=user.is_verified,
                is_agent=user.is_agent,
                is_admin=user.is_admin,
            )
        return User(
            id=200,
            email="agent_reg_test@example.com",
            full_name="Agent Reg Test User",
            is_active=True,
            is_verified=True,
            is_agent=False,
            is_admin=False,
        )
    finally:
        db.close()


@pytest.fixture(autouse=True)
def auth_override_agent_reg():
    app.dependency_overrides[get_current_user] = override_get_current_user_agent_reg
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
def setup_agent_reg_test_user_and_wallet(test_db: Session):
    test_db.query(Transaction).delete()
    test_db.query(Agent).delete()
    test_db.query(Wallet).delete()
    test_db.query(User).delete()
    test_db.commit()

    user = User(
        id=200,
        email="agent_reg_test@example.com",
        full_name="Agent Reg Test User",
        password_hash="hashed_password",
        is_active=True,
        is_verified=True,
        is_agent=False,
    )
    test_db.add(user)
    test_db.commit()
    wallet = Wallet(user_id=user.id, currency="GHS", balance=0.0)
    test_db.add(wallet)
    test_db.commit()
    settings.AGENT_REGISTRATION_FEE = 100.0
    settings.AGENT_STARTUP_LOAN_AMOUNT = 50.0
    yield


def test_initiate_agent_registration_success(test_db: Session, client: TestClient):
    with patch.object(
        PaystackService,
        "initiate_payment",
        new=AsyncMock(
            return_value={
                "authorization_url": "https://paystack.com/pay/agent_reg_test_ref",
                "access_code": "agent_reg_access_code",
                "reference": "agent_reg_test_ref",
            }
        ),
    ):
        response = client.post("/agents/register")

    assert response.status_code == 200
    data = response.json()
    assert data["authorization_url"] == "https://paystack.com/pay/agent_reg_test_ref"
    assert data["reference"] == "agent_reg_test_ref"
    assert "payment initiated" in data["message"].lower()

    agent = test_db.query(Agent).filter(Agent.user_id == 200).first()
    assert agent is not None
    assert agent.status == "pending"

    transaction = test_db.query(Transaction).filter(
        Transaction.provider_reference == "agent_reg_test_ref",
        Transaction.type == "agent_registration_fee",
    ).first()
    assert transaction is not None
    assert transaction.status == "pending"
    assert transaction.amount == settings.AGENT_REGISTRATION_FEE
    assert transaction.provider == "paystack"
    assert transaction.wallet_id is not None


def test_initiate_agent_registration_already_agent(test_db: Session, client: TestClient):
    user = test_db.query(User).filter(User.id == 200).first()
    user.is_agent = True
    test_db.add(user)
    test_db.commit()

    with patch.object(PaystackService, "initiate_payment", new=AsyncMock()) as mocked_initiate:
        response = client.post("/agents/register")

    assert response.status_code == 400
    assert "already an agent" in response.json()["detail"].lower()
    mocked_initiate.assert_not_awaited()


def test_verify_agent_registration_success(test_db: Session, client: TestClient):
    user = test_db.query(User).filter(User.id == 200).first()
    wallet = test_db.query(Wallet).filter(Wallet.user_id == user.id).first()
    agent = Agent(user_id=user.id, status="pending", float_balance=0.0)
    test_db.add(agent)
    transaction = Transaction(
        user_id=user.id,
        wallet_id=wallet.id,
        type="agent_registration_fee",
        amount=settings.AGENT_REGISTRATION_FEE,
        currency="GHS",
        status="pending",
        provider="paystack",
        provider_reference="verify_agent_ref",
    )
    test_db.add(transaction)
    test_db.commit()

    with patch.object(
        PaystackService,
        "verify_payment",
        new=AsyncMock(
            return_value={
                "amount": settings.AGENT_REGISTRATION_FEE * 100,
                "currency": "GHS",
                "status": "success",
                "reference": "verify_agent_ref",
                "customer": {"email": user.email},
            }
        ),
    ):
        response = client.get("/agents/register/verify/verify_agent_ref")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "active"
    assert data["user_id"] == user.id

    test_db.expire_all()
    updated_user = test_db.query(User).filter(User.id == 200).first()
    assert updated_user.is_agent is True
    completed_transaction = test_db.query(Transaction).filter(Transaction.provider_reference == "verify_agent_ref").first()
    assert completed_transaction.status == "completed"
    activated_agent = test_db.query(Agent).filter(Agent.user_id == user.id).first()
    assert activated_agent.status == "active"
    assert activated_agent.float_balance == settings.AGENT_STARTUP_LOAN_AMOUNT

    startup_tx = test_db.query(Transaction).filter(
        Transaction.agent_id == activated_agent.id,
        Transaction.type == "agent_startup_loan_credit",
        Transaction.status == "completed",
    ).first()
    assert startup_tx is not None
    assert startup_tx.amount == settings.AGENT_STARTUP_LOAN_AMOUNT


def test_verify_agent_registration_failed_payment(test_db: Session, client: TestClient):
    user = test_db.query(User).filter(User.id == 200).first()
    wallet = test_db.query(Wallet).filter(Wallet.user_id == user.id).first()
    agent = Agent(user_id=user.id, status="pending", float_balance=0.0)
    test_db.add(agent)
    transaction = Transaction(
        user_id=user.id,
        wallet_id=wallet.id,
        type="agent_registration_fee",
        amount=settings.AGENT_REGISTRATION_FEE,
        currency="GHS",
        status="pending",
        provider="paystack",
        provider_reference="failed_verify_agent_ref",
    )
    test_db.add(transaction)
    test_db.commit()

    with patch.object(
        PaystackService,
        "verify_payment",
        new=AsyncMock(
            return_value={
                "amount": settings.AGENT_REGISTRATION_FEE * 100,
                "currency": "GHS",
                "status": "failed",
                "reference": "failed_verify_agent_ref",
                "customer": {"email": user.email},
            }
        ),
    ):
        response = client.get("/agents/register/verify/failed_verify_agent_ref")

    assert response.status_code == 400
    assert "verification failed: failed" in response.json()["detail"].lower()

    test_db.expire_all()
    failed_transaction = test_db.query(Transaction).filter(Transaction.provider_reference == "failed_verify_agent_ref").first()
    assert failed_transaction.status == "failed"
    current_agent = test_db.query(Agent).filter(Agent.user_id == user.id).first()
    assert current_agent.status == "pending"
    updated_user = test_db.query(User).filter(User.id == 200).first()
    assert updated_user.is_agent is False


def test_verify_agent_registration_pending_keeps_transaction_pending(test_db: Session, client: TestClient):
    user = test_db.query(User).filter(User.id == 200).first()
    wallet = test_db.query(Wallet).filter(Wallet.user_id == user.id).first()
    agent = Agent(user_id=user.id, status="pending", float_balance=0.0)
    test_db.add(agent)
    transaction = Transaction(
        user_id=user.id,
        wallet_id=wallet.id,
        type="agent_registration_fee",
        amount=settings.AGENT_REGISTRATION_FEE,
        currency="GHS",
        status="pending",
        provider="paystack",
        provider_reference="pending_verify_agent_ref",
    )
    test_db.add(transaction)
    test_db.commit()

    with patch.object(
        PaystackService,
        "verify_payment",
        new=AsyncMock(
            return_value={
                "amount": settings.AGENT_REGISTRATION_FEE * 100,
                "currency": "GHS",
                "status": "pending",
                "reference": "pending_verify_agent_ref",
                "customer": {"email": user.email},
            }
        ),
    ):
        response = client.get("/agents/register/verify/pending_verify_agent_ref")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "pending"
    assert payload["user_id"] == user.id

    test_db.expire_all()
    pending_transaction = test_db.query(Transaction).filter(Transaction.provider_reference == "pending_verify_agent_ref").first()
    assert pending_transaction is not None
    assert pending_transaction.status == "pending"

    updated_user = test_db.query(User).filter(User.id == 200).first()
    assert updated_user.is_agent is False


def test_verify_agent_registration_abandoned_treated_as_pending(test_db: Session, client: TestClient):
    user = test_db.query(User).filter(User.id == 200).first()
    wallet = test_db.query(Wallet).filter(Wallet.user_id == user.id).first()
    agent = Agent(user_id=user.id, status="pending", float_balance=0.0)
    test_db.add(agent)
    transaction = Transaction(
        user_id=user.id,
        wallet_id=wallet.id,
        type="agent_registration_fee",
        amount=settings.AGENT_REGISTRATION_FEE,
        currency="GHS",
        status="pending",
        provider="paystack",
        provider_reference="abandoned_verify_agent_ref",
    )
    test_db.add(transaction)
    test_db.commit()

    with patch.object(
        PaystackService,
        "verify_payment",
        new=AsyncMock(
            return_value={
                "amount": settings.AGENT_REGISTRATION_FEE * 100,
                "currency": "GHS",
                "status": "abandoned",
                "reference": "abandoned_verify_agent_ref",
                "customer": {"email": user.email},
            }
        ),
    ):
        response = client.get("/agents/register/verify/abandoned_verify_agent_ref")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "pending"
    assert payload["user_id"] == user.id

    test_db.expire_all()
    pending_transaction = test_db.query(Transaction).filter(
        Transaction.provider_reference == "abandoned_verify_agent_ref"
    ).first()
    assert pending_transaction is not None
    assert pending_transaction.status == "pending"

    updated_user = test_db.query(User).filter(User.id == 200).first()
    assert updated_user.is_agent is False
