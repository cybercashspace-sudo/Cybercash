import pytest
import json
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.models import User, Agent, Wallet, LedgerEntry, JournalEntry
from backend.core.security import create_access_token
from backend.schemas.agent import AgentCreate
from backend.core.config import settings

@pytest.fixture
def test_user(db_session: Session):
    user = User()
    user.email="testagent@example.com"
    user.password_hash="hashedtestpassword"
    user.is_admin=False
    user.is_active=True
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # Ensure the user has a wallet with sufficient balance for registration fee
    wallet = Wallet(user_id=user.id, balance=settings.AGENT_REGISTRATION_FEE + 500, currency="GHS")
    db_session.add(wallet)
    db_session.commit()
    db_session.refresh(wallet)
    
    return user

@pytest.fixture
def test_user_auth_headers(test_user: User):
    access_token = create_access_token(data={"sub": test_user.email})
    return {"Authorization": f"Bearer {access_token}"}

@pytest.fixture
def test_agent(db_session: Session, test_user: User):
    agent = Agent(
        user_id=test_user.id,
        status="active",
        commission_rate=0.05, # Example commission rate
        float_balance=500.0 # Example initial float balance
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent

@pytest.fixture
def agent_auth_headers(test_agent: Agent, test_user: User):
    access_token = create_access_token(data={"sub": test_user.email})
    return {"Authorization": f"Bearer {access_token}"}


def test_create_agent_profile_success(client: TestClient, db_session: Session, test_user: User, test_user_auth_headers: dict):
    initial_wallet_balance = db_session.query(Wallet).filter(Wallet.user_id == test_user.id).first().balance
    
    agent_data = {
        "user_id": test_user.id,
        "status": "pending",
        "commission_rate": 0.05,
        "float_balance": 0.0
    }
    response = client.post("/agents/", json=agent_data, headers=test_user_auth_headers)
    
    assert response.status_code == 201
    response_json = response.json()
    assert response_json["user_id"] == test_user.id
    assert response_json["status"] == "pending"
    assert response_json["float_balance"] == settings.AGENT_STARTUP_LOAN_AMOUNT
    assert "id" in response_json

    # Verify registration fee deduction from wallet
    updated_wallet = db_session.query(Wallet).filter(Wallet.user_id == test_user.id).first()
    assert updated_wallet.balance == initial_wallet_balance - settings.AGENT_REGISTRATION_FEE

    # Verify ledger entries for registration fee
    journal_entry = db_session.query(JournalEntry).filter(
        JournalEntry.description.like(f"Agent registration fee for user {test_user.id}")
    ).first()
    assert journal_entry is not None

    ledger_entries = db_session.query(LedgerEntry).filter(LedgerEntry.journal_entry_id == journal_entry.id).all()
    assert len(ledger_entries) == 2

    # Check for debit to Customer Wallets (Liability)
    customer_wallet_debit = next((e for e in ledger_entries if "Customer Wallets (Liability)" in e.account.name), None)
    assert customer_wallet_debit is not None
    assert customer_wallet_debit.debit == settings.AGENT_REGISTRATION_FEE
    assert customer_wallet_debit.credit == 0.0

    # Check for credit to Revenue - Agent Fees
    revenue_credit = next((e for e in ledger_entries if "Revenue - Agent Fees" in e.account.name), None)
    assert revenue_credit is not None
    assert revenue_credit.debit == 0.0
    assert revenue_credit.credit == settings.AGENT_REGISTRATION_FEE


def test_create_agent_profile_already_exists(client: TestClient, db_session: Session, test_agent: Agent, agent_auth_headers: dict):
    agent_data = {
        "user_id": test_agent.user_id, # Attempt to create an agent for a user who already has one
        "status": "pending",
        "commission_rate": 0.05,
        "float_balance": 0.0
    }
    response = client.post("/agents/", json=agent_data, headers=agent_auth_headers)
    assert response.status_code == 400
    assert "User already has an agent profile" in response.json()["detail"]


def test_create_agent_profile_insufficient_wallet_balance(client: TestClient, db_session: Session, test_user: User, test_user_auth_headers: dict):
    # Set user's wallet balance to be less than registration fee
    wallet = db_session.query(Wallet).filter(Wallet.user_id == test_user.id).first()
    wallet.balance = settings.AGENT_REGISTRATION_FEE - 100 
    db_session.commit()
    db_session.refresh(wallet)

    agent_data = {
        "user_id": test_user.id,
        "status": "pending",
        "commission_rate": 0.05,
        "float_balance": 0.0
    }
    response = client.post("/agents/", json=agent_data, headers=test_user_auth_headers)
    assert response.status_code == 400
    assert "Insufficient wallet balance to pay registration fee" in response.json()["detail"]


@pytest.fixture
def active_agent_user_with_float(db_session: Session):
    user = User()
    user.email="activeagent@example.com"
    user.password_hash="hashedpassword"
    user.is_active=True
    db_session.add(user)
    db_session.flush()

    wallet = Wallet(user_id=user.id, balance=1000.0, currency="GHS") # A separate wallet
    db_session.add(wallet)
    db_session.flush()

    agent = Agent(user_id=user.id, status="active", commission_rate=0.05, float_balance=500.0)
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(user)
    db_session.refresh(agent)
    return user

@pytest.fixture
def active_agent_user_with_float_headers(active_agent_user_with_float: User):
    access_token = create_access_token(data={"sub": active_agent_user_with_float.email})
    return {"Authorization": f"Bearer {access_token}"}


def test_agent_deposit_cash_success(client: TestClient, db_session: Session, active_agent_user_with_float: User, active_agent_user_with_float_headers: dict):
    from backend.models import Payment, Transaction # Import here to avoid circular dependency with other models
    initial_float = active_agent_user_with_float.agent.float_balance
    deposit_amount = 100.0
    
    response = client.post(
        "/agents/me/deposit-cash",
        json={"amount": deposit_amount, "currency": "GHS"},
        headers=active_agent_user_with_float_headers
    )
    
    assert response.status_code == 200
    assert response.json()["float_balance"] == initial_float + deposit_amount

    # Verify Payment record
    payment = db_session.query(Payment).filter_by(agent_id=active_agent_user_with_float.agent.id, type="agent_cash_deposit").first()
    assert payment is not None
    assert payment.amount == deposit_amount
    assert payment.status == "successful"

    # Verify Transaction record
    transaction = db_session.query(Transaction).filter_by(agent_id=active_agent_user_with_float.agent.id, type="agent_float_cash_deposit").first()
    assert transaction is not None
    assert transaction.amount == deposit_amount
    assert transaction.status == "completed"

    # Verify ledger entries
    journal_entry = db_session.query(JournalEntry).filter(
        JournalEntry.description.like(f"Agent {active_agent_user_with_float.agent.id} cash deposit to float")
    ).first()
    assert journal_entry is not None

    ledger_entries = db_session.query(LedgerEntry).filter(LedgerEntry.journal_entry_id == journal_entry.id).all()
    assert len(ledger_entries) == 2

    cash_float_debit = next((e for e in ledger_entries if "Cash (Agent Float)" in e.account.name), None)
    assert cash_float_debit is not None
    assert cash_float_debit.debit == deposit_amount
    assert cash_float_debit.credit == 0.0

    revenue_credit = next((e for e in ledger_entries if "Revenue - Cash Deposits (Agent)" in e.account.name), None)
    assert revenue_credit is not None
    assert revenue_credit.debit == 0.0
    assert revenue_credit.credit == deposit_amount


def test_agent_deposit_cash_invalid_amount(client: TestClient, active_agent_user_with_float_headers: dict):
    response = client.post(
        "/agents/me/deposit-cash",
        json={"amount": 0.0, "currency": "GHS"},
        headers=active_agent_user_with_float_headers
    )
    assert response.status_code == 400
    assert "Deposit amount must be positive" in response.json()["detail"]

    response = client.post(
        "/agents/me/deposit-cash",
        json={"amount": -50.0, "currency": "GHS"},
        headers=active_agent_user_with_float_headers
    )
    assert response.status_code == 400
    assert "Deposit amount must be positive" in response.json()["detail"]


def test_agent_deposit_cash_agent_profile_not_found(client: TestClient, db_session: Session, test_user_auth_headers: dict):
    # User has no agent profile
    response = client.post(
        "/agents/me/deposit-cash",
        json={"amount": 100.0, "currency": "GHS"},
        headers=test_user_auth_headers
    )
    assert response.status_code == 404
    assert "Agent profile not found for current user" in response.json()["detail"]


def test_agent_sell_airtime_success(client: TestClient, db_session: Session, active_agent_user_with_float: User, active_agent_user_with_float_headers: dict):
    from backend.models import Payment, Transaction # Import here if not already at top
    initial_float = active_agent_user_with_float.agent.float_balance
    airtime_amount = 50.0
    commission_rate = active_agent_user_with_float.agent.commission_rate
    commission_earned = airtime_amount * commission_rate
    amount_to_deduct = airtime_amount # Assuming agent pays full cost for now, commission settled separately

    # Mock MomoService to return successful for this specific call
    from unittest.mock import patch
    with patch("backend.services.momo.MomoService.initiate_airtime_payment") as mock_momo:
        mock_momo.return_value = {"status": "successful", "message": "Airtime bought", "processor_transaction_id": "MOMO_AIR_TEST_ID"}

        response = client.post(
            "/agents/me/sell-airtime",
            json={
                "phone_number": "233241234567",
                "amount": airtime_amount,
                "currency": "GHS",
                "network_provider": "MTN"
            },
            headers=active_agent_user_with_float_headers
        )
    
    assert response.status_code == 200
    assert response.json()["float_balance"] == initial_float - amount_to_deduct

    # Verify Payment record
    payment = db_session.query(Payment).filter_by(agent_id=active_agent_user_with_float.agent.id, type="agent_airtime_sale").first()
    assert payment is not None
    assert payment.amount == airtime_amount
    assert payment.status == "successful"
    assert json.loads(payment.metadata_json)["commission_earned"] == commission_earned

    # Verify Transaction record
    transaction = db_session.query(Transaction).filter_by(agent_id=active_agent_user_with_float.agent.id, type="agent_airtime_sale").first()
    assert transaction is not None
    assert transaction.amount == airtime_amount
    assert transaction.status == "completed"
    assert transaction.commission_earned == commission_earned

    # Verify ledger entries
    journal_entry = db_session.query(JournalEntry).filter(
        JournalEntry.description.like(f"Agent {active_agent_user_with_float.agent.id} airtime sale to 233241234567")
    ).first()
    assert journal_entry is not None

    ledger_entries = db_session.query(LedgerEntry).filter(LedgerEntry.journal_entry_id == journal_entry.id).all()
    assert len(ledger_entries) == 4 # Float decrease, Revenue, Commission Expense, Accounts Payable

    # Debit to Cash (Agent Float)
    cash_float_debit = next((e for e in ledger_entries if "Cash (Agent Float)" in e.account.name), None)
    assert cash_float_debit is not None
    assert cash_float_debit.debit == 0.0 # It's a credit to float
    assert cash_float_debit.credit == amount_to_deduct

    # Credit to Revenue - Airtime Sales
    revenue_credit = next((e for e in ledger_entries if "Revenue - Airtime Sales" in e.account.name), None)
    assert revenue_credit is not None
    assert revenue_credit.debit == 0.0
    assert revenue_credit.credit == airtime_amount

    # Debit to Commission Expense (Agent)
    commission_expense_debit = next((e for e in ledger_entries if "Commission Expense (Agent)" in e.account.name), None)
    assert commission_expense_debit is not None
    assert commission_expense_debit.debit == commission_earned
    assert commission_expense_debit.credit == 0.0

    # Credit to Accounts Payable (Agent Commission)
    accounts_payable_credit = next((e for e in ledger_entries if "Accounts Payable (Agent Commission)" in e.account.name), None)
    assert accounts_payable_credit is not None
    assert accounts_payable_credit.debit == 0.0
    assert accounts_payable_credit.credit == commission_earned


def test_agent_sell_airtime_insufficient_float(client: TestClient, active_agent_user_with_float: User, active_agent_user_with_float_headers: dict):
    airtime_amount = active_agent_user_with_float.agent.float_balance + 100 # More than float balance
    
    response = client.post(
        "/agents/me/sell-airtime",
        json={
            "phone_number": "233241234567",
            "amount": airtime_amount,
            "currency": "GHS",
            "network_provider": "MTN"
        },
        headers=active_agent_user_with_float_headers
    )
    assert response.status_code == 400
    assert "Insufficient float balance to sell airtime" in response.json()["detail"]


def test_agent_sell_airtime_invalid_amount(client: TestClient, active_agent_user_with_float_headers: dict):
    response = client.post(
        "/agents/me/sell-airtime",
        json={
            "phone_number": "233241234567",
            "amount": 0.0,
            "currency": "GHS",
            "network_provider": "MTN"
        },
        headers=active_agent_user_with_float_headers
    )
    assert response.status_code == 400
    assert "Airtime amount must be positive" in response.json()["detail"]


def test_agent_sell_airtime_agent_profile_not_found(client: TestClient, db_session: Session, test_user_auth_headers: dict):
    # User has no agent profile
    response = client.post(
        "/agents/me/sell-airtime",
        json={
            "phone_number": "233241234567",
            "amount": 50.0,
            "currency": "GHS",
            "network_provider": "MTN"
        },
        headers=test_user_auth_headers
    )
    assert response.status_code == 404
    assert "Agent profile not found for current user" in response.json()["detail"]


def test_agent_sell_airtime_momo_service_failure_reverts_float(client: TestClient, db_session: Session, active_agent_user_with_float: User, active_agent_user_with_float_headers: dict):
    initial_float = active_agent_user_with_float.agent.float_balance
    airtime_amount = 50.0

    # Mock MomoService to return failed status
    from unittest.mock import patch
    with patch("backend.services.momo.MomoService.initiate_airtime_payment") as mock_momo:
        mock_momo.return_value = {"status": "failed", "message": "Momo service error"}

        response = client.post(
            "/agents/me/sell-airtime",
            json={
                "phone_number": "233241234567",
                "amount": airtime_amount,
                "currency": "GHS",
                "network_provider": "MTN"
            },
            headers=active_agent_user_with_float_headers
        )
    
    assert response.status_code == 500
    assert "Momo service error" in response.json()["detail"]

    # Verify that agent's float balance was reverted
    db_session.refresh(active_agent_user_with_float.agent)
    assert active_agent_user_with_float.agent.float_balance == initial_float


def test_agent_sell_data_bundle_success(client: TestClient, db_session: Session, active_agent_user_with_float: User, active_agent_user_with_float_headers: dict):
    from backend.models import Payment, Transaction # Import here if not already at top
    initial_float = active_agent_user_with_float.agent.float_balance
    data_bundle_amount = 75.0
    commission_rate = active_agent_user_with_float.agent.commission_rate
    commission_earned = data_bundle_amount * commission_rate
    amount_to_deduct = data_bundle_amount

    # Mock MomoService to return successful for this specific call
    from unittest.mock import patch
    with patch("backend.services.momo.MomoService.initiate_data_bundle_payment") as mock_momo:
        mock_momo.return_value = {"status": "successful", "message": "Data bundle bought", "processor_transaction_id": "MOMO_DATA_TEST_ID"}

        response = client.post(
            "/agents/me/sell-data-bundle",
            json={
                "phone_number": "233241234567",
                "amount": data_bundle_amount,
                "currency": "GHS",
                "network_provider": "Vodafone"
            },
            headers=active_agent_user_with_float_headers
        )
    
    assert response.status_code == 200
    assert response.json()["float_balance"] == initial_float - amount_to_deduct

    # Verify Payment record
    payment = db_session.query(Payment).filter_by(agent_id=active_agent_user_with_float.agent.id, type="agent_data_bundle_sale").first()
    assert payment is not None
    assert payment.amount == data_bundle_amount
    assert payment.status == "successful"
    assert json.loads(payment.metadata_json)["commission_earned"] == commission_earned

    # Verify Transaction record
    transaction = db_session.query(Transaction).filter_by(agent_id=active_agent_user_with_float.agent.id, type="agent_data_bundle_sale").first()
    assert transaction is not None
    assert transaction.amount == data_bundle_amount
    assert transaction.status == "completed"
    assert transaction.commission_earned == commission_earned

    # Verify ledger entries
    journal_entry = db_session.query(JournalEntry).filter(
        JournalEntry.description.like(f"Agent {active_agent_user_with_float.agent.id} data bundle sale to 233241234567")
    ).first()
    assert journal_entry is not None

    ledger_entries = db_session.query(LedgerEntry).filter(LedgerEntry.journal_entry_id == journal_entry.id).all()
    assert len(ledger_entries) == 4 # Float decrease, Revenue, Commission Expense, Accounts Payable

    # Debit to Cash (Agent Float)
    cash_float_debit = next((e for e in ledger_entries if "Cash (Agent Float)" in e.account.name), None)
    assert cash_float_debit is not None
    assert cash_float_debit.debit == 0.0 # It's a credit to float
    assert cash_float_debit.credit == amount_to_deduct

    # Credit to Revenue - Data Bundle Sales
    revenue_credit = next((e for e in ledger_entries if "Revenue - Data Bundle Sales" in e.account.name), None)
    assert revenue_credit is not None
    assert revenue_credit.debit == 0.0
    assert revenue_credit.credit == data_bundle_amount

    # Debit to Commission Expense (Agent)
    commission_expense_debit = next((e for e in ledger_entries if "Commission Expense (Agent)" in e.account.name), None)
    assert commission_expense_debit is not None
    assert commission_expense_debit.debit == commission_earned
    assert commission_expense_debit.credit == 0.0

    # Credit to Accounts Payable (Agent Commission)
    accounts_payable_credit = next((e for e in ledger_entries if "Accounts Payable (Agent Commission)" in e.account.name), None)
    assert accounts_payable_credit is not None
    assert accounts_payable_credit.debit == 0.0
    assert accounts_payable_credit.credit == commission_earned


def test_agent_sell_data_bundle_insufficient_float(client: TestClient, active_agent_user_with_float: User, active_agent_user_with_float_headers: dict):
    data_bundle_amount = active_agent_user_with_float.agent.float_balance + 100 # More than float balance
    
    response = client.post(
        "/agents/me/sell-data-bundle",
        json={
            "phone_number": "233241234567",
            "amount": data_bundle_amount,
            "currency": "GHS",
            "network_provider": "Vodafone"
        },
        headers=active_agent_user_with_float_headers
    )
    assert response.status_code == 400
    assert "Insufficient float balance to sell data bundle" in response.json()["detail"]


def test_agent_sell_data_bundle_invalid_amount(client: TestClient, active_agent_user_with_float_headers: dict):
    response = client.post(
        "/agents/me/sell-data-bundle",
        json={
            "phone_number": "233241234567",
            "amount": 0.0,
            "currency": "GHS",
            "network_provider": "Vodafone"
        },
        headers=active_agent_user_with_float_headers
    )
    assert response.status_code == 400
    assert "Data bundle amount must be positive" in response.json()["detail"]


def test_agent_sell_data_bundle_agent_profile_not_found(client: TestClient, db_session: Session, test_user_auth_headers: dict):
    # User has no agent profile
    response = client.post(
        "/agents/me/sell-data-bundle",
        json={
            "phone_number": "233241234567",
            "amount": 50.0,
            "currency": "GHS",
            "network_provider": "Vodafone"
        },
        headers=test_user_auth_headers
    )
    assert response.status_code == 404
    assert "Agent profile not found for current user" in response.json()["detail"]


def test_agent_sell_data_bundle_momo_service_failure_reverts_float(client: TestClient, db_session: Session, active_agent_user_with_float: User, active_agent_user_with_float_headers: dict):
    initial_float = active_agent_user_with_float.agent.float_balance
    data_bundle_amount = 50.0

    # Mock MomoService to return failed status
    from unittest.mock import patch
    with patch("backend.services.momo.MomoService.initiate_data_bundle_payment") as mock_momo:
        mock_momo.return_value = {"status": "failed", "message": "Momo service error"}

        response = client.post(
            "/agents/me/sell-data-bundle",
            json={
                "phone_number": "233241234567",
                "amount": data_bundle_amount,
                "currency": "GHS",
                "network_provider": "Vodafone"
            },
            headers=active_agent_user_with_float_headers
        )
    
    assert response.status_code == 500
    assert "Momo service error" in response.json()["detail"]

    # Verify that agent's float balance was reverted
    db_session.refresh(active_agent_user_with_float.agent)
    assert active_agent_user_with_float.agent.float_balance == initial_float
