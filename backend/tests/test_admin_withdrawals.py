import pytest
from fastapi.testclient import TestClient # Keep for type hinting, though client will be a fixture
from sqlalchemy.orm import Session # Added for type hinting

# Import app to ensure all models are loaded via its dependencies
from backend.main import app
from backend.database import Base, get_db # Import Base explicitly here
from backend.models import User, Payment, CryptoTransaction, Account 

# Explicitly import all model modules at the top level
# This ensures Base.metadata knows about all models when create_all is called.
import backend.models.user
import backend.models.account
import backend.models.agent
import backend.models.cryptotransaction
import backend.models.cryptowallet
import backend.models.journalentry
import backend.models.ledgerentry
import backend.models.payment
import backend.models.transaction
import backend.models.virtualcard
import backend.models.wallet


from backend.core.security import create_access_token
from backend.services.ledger_service import LedgerService, get_ledger_service
from backend.services.momo import MomoService
from backend.services.crypto import CryptoService
from backend.services.bank import BankService

# All fixtures and test database setup will be moved to conftest.py

# --- Test Cases ---

# Changed to def from async def, removed await from client calls
def test_initiate_bank_withdrawal_admin_success(client: TestClient, admin_auth_headers: dict, db_session: Session): # Changed type hint
    response = client.post( # Removed await
        "/admin/withdrawals/bank/initiate", # Corrected URL path
        headers=admin_auth_headers,
        json={
            "amount": 100.0,
            "currency": "GHS",
            "bank_name": "Test Bank",
            "account_name": "Admin Payout",
            "account_number": "1234567890",
            "swift_code": "TESTSWIFT",
            "notes": "Admin bank payout test"
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["amount"] == 100.0
    assert data["processor"] == "bank"
    assert data["status"] == "pending"

    # Verify Payment record
    payment = db_session.query(Payment).filter_by(id=data["id"]).first()
    assert payment is not None
    assert payment.amount == 100.0
    assert payment.status == "pending"
    assert payment.processor_transaction_id == "BANK_TEST_ID"

    # Verify Ledger entries
    cash_account = db_session.query(Account).filter_by(name="Cash (External Bank)").first()
    revenue_payout_account = db_session.query(Account).filter_by(name="Revenue Payout (Expense)").first()
    assert cash_account.balance == -100.0 # Credited
    assert revenue_payout_account.balance == 100.0 # Debited

# Changed to def from async def, removed await from client calls
def test_initiate_bank_withdrawal_admin_invalid_amount(client: TestClient, admin_auth_headers: dict, db_session: Session): # Changed type hint
    response = client.post( # Removed await
        "/admin/withdrawals/bank/initiate", # Corrected URL path
        headers=admin_auth_headers,
        json={
            "amount": -10.0,
            "currency": "GHS",
            "bank_name": "Test Bank",
            "account_name": "Admin Payout",
            "account_number": "1234567890",
        },
    )
    assert response.status_code == 422 # Unprocessable Entity for Pydantic validation error

# Changed to def from async def, removed await from client calls
def test_initiate_bank_withdrawal_admin_unauthorized(client: TestClient, db_session: Session): # Changed type hint - no admin_auth_headers
    response = client.post( # Removed await
        "/admin/withdrawals/bank/initiate", # Corrected URL path
        json={
            "amount": 100.0,
            "currency": "GHS",
            "bank_name": "Test Bank",
            "account_name": "Admin Payout",
            "account_number": "1234567890",
        },
    )
    assert response.status_code == 401 # Unauthorized (missing bearer token)


# Changed to def from async def, removed await from client calls
def test_initiate_momo_withdrawal_admin_success(client: TestClient, admin_auth_headers: dict, db_session: Session): # Changed type hint
    response = client.post( # Removed await
        "/admin/withdrawals/momo/initiate", # Corrected URL path
        headers=admin_auth_headers,
        json={
            "amount": 50.0,
            "currency": "GHS",
            "phone_number": "0241234567",
            "network": "MTN",
            "notes": "Admin momo payout test"
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["amount"] == 50.0
    assert data["processor"] == "momo"
    assert data["status"] == "awaiting_confirmation"

    # Verify Payment record
    payment = db_session.query(Payment).filter_by(id=data["id"]).first()
    assert payment is not None
    assert payment.amount == 50.0
    assert payment.status == "awaiting_confirmation"
    assert payment.processor_transaction_id == "MOMO_TEST_ID"

    # Verify Ledger entries
    cash_account = db_session.query(Account).filter_by(name="Cash (External Bank)").first()
    revenue_payout_account = db_session.query(Account).filter_by(name="Revenue Payout (Expense)").first()
    assert cash_account.balance == -50.0 # Credited
    assert revenue_payout_account.balance == 50.0 # Debited

# Changed to def from async def, removed await from client calls
def test_initiate_crypto_withdrawal_admin_success(client: TestClient, admin_auth_headers: dict, db_session: Session): # Changed type hint
    response = client.post( # Removed await
        "/admin/withdrawals/crypto/initiate", # Corrected URL path
        headers=admin_auth_headers,
        json={
            "amount": 0.001,
            "currency": "USD",
            "coin_type": "BTC",
            "to_address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            "fee": 0.00005,
            "notes": "Admin crypto payout test"
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["amount"] == 0.001
    assert data["coin_type"] == "BTC"
    assert data["status"] == "awaiting_confirmation"
    assert data["transaction_hash"] == "CRYPTO_TEST_HASH"

    # Verify CryptoTransaction record
    crypto_transaction = db_session.query(CryptoTransaction).filter_by(id=data["id"]).first()
    assert crypto_transaction is not None
    assert crypto_transaction.amount == 0.001
    assert crypto_transaction.fee == 0.00005
    assert crypto_transaction.status == "awaiting_confirmation"

    # Verify Ledger entries
    crypto_hot_wallet_account = db_session.query(Account).filter_by(name="Crypto Hot Wallet (Asset)").first()
    revenue_payout_account = db_session.query(Account).filter_by(name="Revenue Payout (Expense)").first()
    # Total amount = amount + fee
    assert crypto_hot_wallet_account.balance == -(0.001 + 0.00005) # Credited
    assert revenue_payout_account.balance == (0.001 + 0.00005) # Debited
