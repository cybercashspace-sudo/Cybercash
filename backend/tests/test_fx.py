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

    # Create wallets for the user
    ghs_wallet = Wallet(user_id=user.id, currency="GHS", balance=1000.0)
    usd_wallet = Wallet(user_id=user.id, currency="USD", balance=0.0)
    test_db.add_all([ghs_wallet, usd_wallet])
    test_db.commit()
    test_db.refresh(ghs_wallet)
    test_db.refresh(usd_wallet)
    
    settings.FX_SPREAD_PERCENTAGE = 0.01 # Set a known spread for testing

    yield
    test_db.query(LedgerEntry).delete()
    test_db.query(Account).delete()
    test_db.query(Transaction).delete()
    test_db.query(Wallet).delete()
    test_db.query(User).delete()
    test_db.commit()


def test_successful_currency_exchange(test_db: Session):
    response = client.post(
        "/wallet/exchange",
        json={"from_currency": "GHS", "to_currency": "USD", "amount": 100.0}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["from_currency"] == "GHS"
    assert data["to_currency"] == "USD"
    assert data["amount_sent"] == 100.0
    assert data["amount_received"] > 0
    assert data["exchange_rate"] > 0
    assert data["spread_amount"] > 0

    test_db.expire_all()
    user = test_db.query(User).filter(User.id == 500).first()
    ghs_wallet = test_db.query(Wallet).filter(Wallet.user_id == user.id, Wallet.currency == "GHS").first()
    usd_wallet = test_db.query(Wallet).filter(Wallet.user_id == user.id, Wallet.currency == "USD").first()

    assert ghs_wallet.balance == 1000.0 - 100.0
    assert usd_wallet.balance == data["amount_received"]

    # Verify ledger entries
    transactions_for_user = test_db.query(Transaction).filter(Transaction.user_id == user.id, Transaction.type == "fx_exchange").all()
    assert len(transactions_for_user) == 1
    fx_transaction = transactions_for_user[0]
    assert fx_transaction.fx_rate == data["exchange_rate"]
    assert fx_transaction.fx_spread_amount == data["spread_amount"]

    journal_entry = test_db.query(JournalEntry).filter(JournalEntry.transaction_id == fx_transaction.id).first()
    assert journal_entry is not None
    assert len(journal_entry.ledger_entries) == 3 # Debit GHS Liability, Credit USD Liability, Credit FX Revenue

    ghs_liability_account = test_db.query(Account).filter(Account.name == "Customer Wallets (Liability) - GHS").first()
    usd_liability_account = test_db.query(Account).filter(Account.name == "Customer Wallets (Liability) - USD").first()
    fx_revenue_account = test_db.query(Account).filter(Account.name == "Revenue - FX Margins").first()

    assert ghs_liability_account.balance == 100.0
    assert usd_liability_account.balance == -data["amount_received"]
    assert fx_revenue_account.balance == -data["spread_amount"]


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
