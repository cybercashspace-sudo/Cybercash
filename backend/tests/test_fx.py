from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from backend.database import Base, engine
from backend.main import app
from backend.dependencies.auth import get_current_user
from backend.models import User, Wallet, Transaction, LedgerEntry, Account, JournalEntry
from backend.core.config import settings
from backend.services.ledger_service import LedgerService # For initializing accounts
import pytest
import json

# Use a test database
@pytest.fixture(scope="module")
def test_db():
    # Schema setup handled by conftest
    db = Session(bind=engine)
    yield db
    db.close()
    # Schema teardown handled by conftest

# Override get_current_user for testing FX endpoints
def override_get_current_user_fx():
    return User(id=500, email="fx_test@example.com", full_name="FX Test User", is_active=True, is_verified=True)

@pytest.fixture(autouse=True)
def auth_override_fx():
    app.dependency_overrides[get_current_user] = override_get_current_user_fx
    yield
    app.dependency_overrides.pop(get_current_user, None)

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_fx_test_user_and_wallets(test_db: Session):
    # Ensure a clean state for each test
    test_db.query(LedgerEntry).delete()
    test_db.query(Account).delete()
    test_db.query(Transaction).delete()
    test_db.query(Wallet).delete()
    test_db.query(User).delete()
    test_db.commit()

    user = User(id=500, email="fx_test@example.com", full_name="FX Test User", password_hash="hashed_password", is_active=True, is_verified=True)
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)

    # Initialize standard accounts via LedgerService
    ledger_service = LedgerService(test_db) # This will create the accounts

    # Each account has one fiat wallet; multiple currency wallets are not supported.
    ghs_wallet = Wallet(user_id=user.id, currency="GHS", balance=1000.0)
    test_db.add(ghs_wallet)
    test_db.commit()
    test_db.refresh(ghs_wallet)
    
    settings.FX_SPREAD_PERCENTAGE = 0.01 # Set a known spread for testing

    yield
    test_db.query(LedgerEntry).delete()
    test_db.query(Account).delete()
    test_db.query(Transaction).delete()
    test_db.query(Wallet).delete()
    test_db.query(User).delete()
    test_db.commit()


def test_currency_exchange_does_not_create_a_second_wallet(test_db: Session):
    response = client.post(
        "/wallet/exchange",
        json={"from_currency": "GHS", "to_currency": "USD", "amount": 100.0}
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "A separate wallet for the target currency is not available."

    test_db.expire_all()
    wallet = test_db.query(Wallet).filter(Wallet.user_id == 500).one()
    assert wallet.balance == 1000.0
    assert test_db.query(Transaction).filter(Transaction.user_id == 500).count() == 0


def test_currency_exchange_insufficient_funds(test_db: Session):
    response = client.post(
        "/wallet/exchange",
        json={"from_currency": "GHS", "to_currency": "USD", "amount": 2000.0} # More than 1000 in GHS wallet
    )
    assert response.status_code == 400
    assert "Insufficient funds in source wallet." in response.json()["detail"]

def test_currency_exchange_unsupported_currency(test_db: Session):
    response = client.post(
        "/wallet/exchange",
        json={"from_currency": "GHS", "to_currency": "JPY", "amount": 100.0}
    )
    assert response.status_code == 400
    assert "Unsupported currency exchange" in response.json()["detail"]

def test_currency_exchange_same_currency(test_db: Session):
    response = client.post(
        "/wallet/exchange",
        json={"from_currency": "GHS", "to_currency": "GHS", "amount": 100.0}
    )
    assert response.status_code == 400
    assert "Cannot exchange to the same currency." in response.json()["detail"]

def test_currency_exchange_negative_amount(test_db: Session):
    response = client.post(
        "/wallet/exchange",
        json={"from_currency": "GHS", "to_currency": "USD", "amount": -100.0}
    )
    assert response.status_code == 400
    assert "Exchange amount must be positive." in response.json()["detail"]
