from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from backend.database import Base, engine
from backend.main import app
from backend.dependencies.auth import get_current_user
from backend.models import User, Wallet, Transaction, JournalEntry, LedgerEntry, Account
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

# Override get_current_user for testing for ledger views
def override_get_current_user_ledger():
    return User(id=300, email="ledger_viewer@example.com", full_name="Ledger Viewer", is_active=True, is_verified=True)

@pytest.fixture(autouse=True)
def auth_override_ledger():
    app.dependency_overrides[get_current_user] = override_get_current_user_ledger
    yield
    app.dependency_overrides.pop(get_current_user, None)

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_ledger_data(test_db: Session):
    # Ensure a clean state for each test
    test_db.query(LedgerEntry).delete()
    test_db.query(JournalEntry).delete()
    test_db.query(Account).delete()
    test_db.query(Transaction).delete()
    test_db.query(Wallet).delete()
    test_db.query(User).delete()
    test_db.commit()

    user = User(id=300, email="ledger_viewer@example.com", full_name="Ledger Viewer", password_hash="hashed_password", is_active=True, is_verified=True)
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)

    # Create some test data
    wallet = Wallet(user_id=user.id, currency="GHS", balance=100.0)
    test_db.add(wallet)
    test_db.commit()
    test_db.refresh(wallet)

    transaction = Transaction(
        user_id=user.id,
        wallet_id=wallet.id,
        type="deposit",
        amount=100.0,
        currency="GHS",
        status="completed"
    )
    test_db.add(transaction)
    test_db.commit()
    test_db.refresh(transaction)

    cash_account = Account(name="Cash (External Bank)", type="Asset", description="Cash held in external bank accounts.", balance=100.0)
    customer_wallets_account = Account(name="Customer Wallets (Liability)", type="Liability", description="Funds owed to customers.", balance=100.0)
    test_db.add_all([cash_account, customer_wallets_account])
    test_db.commit()
    test_db.refresh(cash_account)
    test_db.refresh(customer_wallets_account)

    journal_entry = JournalEntry(description="Initial deposit by user", transaction_id=transaction.id)
    test_db.add(journal_entry)
    test_db.commit()
    test_db.refresh(journal_entry)

    test_db.add_all([
        LedgerEntry(
            journal_entry_id=journal_entry.id,
            account_id=cash_account.id,
            debit=100.0,
            credit=0.0,
            description="Initial deposit by user",
        ),
        LedgerEntry(
            journal_entry_id=journal_entry.id,
            account_id=customer_wallets_account.id,
            debit=0.0,
            credit=100.0,
            description="Initial deposit by user",
        ),
    ])
    test_db.commit()
    yield
    test_db.query(LedgerEntry).delete()
    test_db.query(JournalEntry).delete()
    test_db.query(Account).delete()
    test_db.query(Transaction).delete()
    test_db.query(Wallet).delete()
    test_db.query(User).delete()
    test_db.commit()


def test_get_all_journal_entries(test_db: Session):
    response = client.get("/ledger/journal_entries")
    assert response.status_code == 200
    journal_entries = response.json()
    assert len(journal_entries) == 1
    assert journal_entries[0]["description"] == "Initial deposit by user"
    assert len(journal_entries[0]["ledger_entries"]) == 2
    
    # Check a debit entry
    debit_entry = next((le for le in journal_entries[0]["ledger_entries"] if le["debit"] > 0), None)
    assert debit_entry is not None
    assert debit_entry["debit"] == 100.0
    
    # Check a credit entry
    credit_entry = next((le for le in journal_entries[0]["ledger_entries"] if le["credit"] > 0), None)
    assert credit_entry is not None
    assert credit_entry["credit"] == 100.0


def test_get_all_account_balances(test_db: Session):
    response = client.get("/ledger/accounts_balance")
    assert response.status_code == 200
    accounts = response.json()
    assert len(accounts) > 0 # Should have all standard accounts

    customer_wallets_account = next((acc for acc in accounts if acc["name"] == "Customer Wallets (Liability)"), None)
    assert customer_wallets_account is not None
    assert customer_wallets_account["balance"] == 100.0

    cash_external_bank_account = next((acc for acc in accounts if acc["name"] == "Cash (External Bank)"), None)
    assert cash_external_bank_account is not None
    assert cash_external_bank_account["balance"] == 100.0
