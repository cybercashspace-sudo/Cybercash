from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from backend.database import Base, engine
from backend.main import app
from backend.dependencies.auth import get_current_user
from backend.models import User, Wallet, Transaction, JournalEntry, LedgerEntry

import pytest

# Use a test database
@pytest.fixture(scope="module")
def test_db():
    # Schema setup handled by conftest
    db = Session(bind=engine)
    yield db
    db.close()
    # Schema teardown handled by conftest

# Override get_current_user for testing
def override_get_current_user():
    return User(id=1, email="test_sender@example.com", full_name="Test Sender", is_active=True, is_verified=True)

@pytest.fixture(autouse=True)
def auth_override_wallet_transfers():
    app.dependency_overrides[get_current_user] = override_get_current_user
    yield
    app.dependency_overrides.pop(get_current_user, None)

client = TestClient(app)

def test_successful_p2p_transfer(test_db: Session):
    # Setup sender and recipient
    sender = User(email="test_sender@example.com", full_name="Test Sender", password_hash="hashed_password", is_active=True, is_verified=True)
    recipient = User(email="test_recipient@example.com", full_name="Test Recipient", password_hash="hashed_password", is_active=True, is_verified=True)
    test_db.add_all([sender, recipient])
    test_db.commit()
    test_db.refresh(sender)
    test_db.refresh(recipient)

    sender_wallet = Wallet(user_id=sender.id, currency="GHS", balance=100.0)
    test_db.add(sender_wallet)
    test_db.commit()
    test_db.refresh(sender_wallet)

    # Perform transfer
    response = client.post(
        "/wallet/transfer",
        json={"recipient_email": "test_recipient@example.com", "amount": 50.0, "currency": "GHS"}
    )
    assert response.status_code == 200
    test_db.expire_all()
    updated_sender_wallet = test_db.query(Wallet).filter(Wallet.user_id == sender.id).first()
    recipient_wallet = test_db.query(Wallet).filter(Wallet.user_id == recipient.id).first()

    assert updated_sender_wallet.balance == 50.0
    assert recipient_wallet.balance == 50.0

    sender_tx = test_db.query(Transaction).filter(
        Transaction.user_id == sender.id,
        Transaction.type == "TRANSFER",
        Transaction.amount == -50.0,
    ).first()
    recipient_tx = test_db.query(Transaction).filter(
        Transaction.user_id == recipient.id,
        Transaction.type == "TRANSFER",
        Transaction.amount == 50.0,
    ).first()
    assert sender_tx is not None
    assert recipient_tx is not None

    journal = test_db.query(JournalEntry).filter(JournalEntry.transaction_id == sender_tx.id).first()
    assert journal is not None
    ledger_rows = test_db.query(LedgerEntry).filter(LedgerEntry.journal_entry_id == journal.id).all()
    assert len(ledger_rows) == 2

def test_transfer_insufficient_funds(test_db: Session):
    sender = User(email="insufficient_sender@example.com", full_name="Insufficient Sender", password_hash="hashed_password", is_active=True, is_verified=True)
    recipient = User(email="insufficient_recipient@example.com", full_name="Insufficient Recipient", password_hash="hashed_password", is_active=True, is_verified=True)
    test_db.add_all([sender, recipient])
    test_db.commit()
    test_db.refresh(sender)
    test_db.refresh(recipient)

    sender_wallet = Wallet(user_id=sender.id, currency="GHS", balance=20.0)
    test_db.add(sender_wallet)
    test_db.commit()
    test_db.refresh(sender_wallet)

    response = client.post(
        "/wallet/transfer",
        json={"recipient_email": "insufficient_recipient@example.com", "amount": 50.0, "currency": "GHS"}
    )
    assert response.status_code == 400
    assert "Insufficient balance" in response.json()["detail"]

def test_transfer_non_existent_recipient(test_db: Session):
    sender = User(email="non_existent_sender@example.com", full_name="Non Existent Sender", password_hash="hashed_password", is_active=True, is_verified=True)
    test_db.add(sender)
    test_db.commit()
    test_db.refresh(sender)

    sender_wallet = Wallet(user_id=sender.id, currency="GHS", balance=100.0)
    test_db.add(sender_wallet)
    test_db.commit()
    test_db.refresh(sender_wallet)

    response = client.post(
        "/wallet/transfer",
        json={"recipient_email": "non_existent@example.com", "amount": 50.0, "currency": "GHS"}
    )
    assert response.status_code == 404
    assert "Recipient user not found" in response.json()["detail"]

def test_transfer_to_self(test_db: Session):
    sender = User(id=1, email="test_sender@example.com", full_name="Test Sender", password_hash="hashed_password", is_active=True, is_verified=True)
    # The override_get_current_user is set to id=1, email="test_sender@example.com"
    # So the sender in this test will be the same as the current user from dependency override.
    test_db.add(sender)
    test_db.commit()
    test_db.refresh(sender)

    sender_wallet = Wallet(user_id=sender.id, currency="GHS", balance=100.0)
    test_db.add(sender_wallet)
    test_db.commit()
    test_db.refresh(sender_wallet)

    response = client.post(
        "/wallet/transfer",
        json={"recipient_email": "test_sender@example.com", "amount": 50.0, "currency": "GHS"}
    )
    assert response.status_code == 400
    assert "Cannot transfer funds to yourself." in response.json()["detail"]

def test_transfer_invalid_amount(test_db: Session):
    sender = User(email="invalid_amount_sender@example.com", full_name="Invalid Amount Sender", password_hash="hashed_password", is_active=True, is_verified=True)
    recipient = User(email="invalid_amount_recipient@example.com", full_name="Invalid Amount Recipient", password_hash="hashed_password", is_active=True, is_verified=True)
    test_db.add_all([sender, recipient])
    test_db.commit()
    test_db.refresh(sender)
    test_db.refresh(recipient)

    sender_wallet = Wallet(user_id=sender.id, currency="GHS", balance=100.0)
    test_db.add(sender_wallet)
    test_db.commit()
    test_db.refresh(sender_wallet)

    # Test with zero amount
    response = client.post(
        "/wallet/transfer",
        json={"recipient_email": "invalid_amount_recipient@example.com", "amount": 0.0, "currency": "GHS"}
    )
    assert response.status_code == 400
    assert "Transfer amount must be positive." in response.json()["detail"]

    # Test with negative amount
    response = client.post(
        "/wallet/transfer",
        json={"recipient_email": "invalid_amount_recipient@example.com", "amount": -10.0, "currency": "GHS"}
    )
    assert response.status_code == 400
    assert "Transfer amount must be positive." in response.json()["detail"]
