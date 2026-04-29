
import pytest
from backend.main import app
from backend.models import User, Agent, Wallet, Account, Transaction
from sqlalchemy import select

# Use the client fixture from conftest.py
# Tests will run against the in-memory SQLite DB set up in conftest.py

def test_agent_cash_deposit_flow(client, db_session, admin_auth_headers):
    # 1. Setup Data
    # Create an Agent
    agent_user = User(email="agent@test.com", password_hash="hash", is_active=True, is_verified=True, is_agent=True)
    db_session.add(agent_user)
    db_session.commit()
    db_session.refresh(agent_user)
    
    agent_wallet = Wallet(user_id=agent_user.id, balance=100.0) # Agent Personal Wallet
    db_session.add(agent_wallet)
    
    agent = Agent(user_id=agent_user.id, status="active", commission_rate=0.02, float_balance=1000.0, commission_balance=0.0)
    db_session.add(agent)
    
    # Create a Customer
    customer = User(email="customer@test.com", password_hash="hash", is_active=True, is_verified=True)
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)
    
    customer_wallet = Wallet(user_id=customer.id, balance=50.0)
    db_session.add(customer_wallet)
    
    db_session.commit()
    
    # Get Agent Auth Token
    from backend.core.security import create_access_token
    agent_token = create_access_token(data={"sub": agent_user.email})
    agent_headers = {"Authorization": f"Bearer {agent_token}"}

    # 2. Perform Cash Deposit
    # Customer gives 200 Cash. Agent sends 200 Digital.
    # Agent Float: 1000 -> 800
    # Customer Wallet: 50 -> 250
    # Agent Commission: 200 * 0.02 = 4.0
    
    response = client.post(
        "/agent-transactions/cash-deposit",
        json={"user_id": customer.id, "amount": 200.0, "currency": "GHS"},
        headers=agent_headers
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "completed"
    assert data["amount"] == 200.0
    
    # 3. Verify Balances
    db_session.refresh(agent)
    db_session.refresh(customer_wallet)
    
    assert agent.float_balance == 800.0
    assert customer_wallet.balance == 250.0
    assert agent.commission_balance == 4.0


def test_agent_cash_deposit_with_topup_fee_credits_net_amount(client, db_session):
    agent_user = User(email="agent_fee@test.com", password_hash="hash", is_active=True, is_verified=True, is_agent=True)
    db_session.add(agent_user)
    db_session.commit()
    db_session.refresh(agent_user)

    agent_wallet = Wallet(user_id=agent_user.id, balance=0.0)
    db_session.add(agent_wallet)

    agent = Agent(user_id=agent_user.id, status="active", commission_rate=0.02, float_balance=1000.0, commission_balance=0.0)
    db_session.add(agent)

    customer = User(
        email="customer_fee@test.com",
        phone_number="0241000999",
        password_hash="hash",
        is_active=True,
        is_verified=True,
    )
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)

    customer_wallet = Wallet(user_id=customer.id, balance=50.0)
    db_session.add(customer_wallet)
    db_session.commit()

    from backend.core.security import create_access_token

    agent_token = create_access_token(data={"sub": agent_user.email})
    agent_headers = {"Authorization": f"Bearer {agent_token}"}

    response = client.post(
        "/agent-transactions/cash-deposit",
        json={
            "customer_phone": customer.phone_number,
            "amount": 10.0,
            "currency": "GHS",
            "topup_fee_rate": 0.05,
        },
        headers=agent_headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert round(float(data["amount"]), 2) == 9.5

    db_session.refresh(agent)
    db_session.refresh(customer_wallet)

    assert round(agent.float_balance, 2) == 990.5
    assert round(customer_wallet.balance, 2) == 59.5
    assert round(agent.commission_balance, 2) == 0.2

def test_agent_cash_withdrawal_flow(client, db_session):
    # 1. Setup Data
    # Create an Agent
    agent_user = User(email="agent_w@test.com", password_hash="hash", is_active=True, is_verified=True, is_agent=True)
    db_session.add(agent_user)
    db_session.commit()
    db_session.refresh(agent_user)
    
    agent_wallet = Wallet(user_id=agent_user.id, balance=0.0)
    db_session.add(agent_wallet)
    
    agent = Agent(user_id=agent_user.id, status="active", commission_rate=0.02, float_balance=500.0, commission_balance=0.0)
    db_session.add(agent)
    
    # Create a Customer with funds
    customer = User(email="customer_w@test.com", password_hash="hash", is_active=True, is_verified=True)
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)
    
    customer_wallet = Wallet(user_id=customer.id, balance=300.0)
    db_session.add(customer_wallet)
    
    db_session.commit()
    
    # Get Agent Auth Token
    from backend.core.security import create_access_token
    agent_token = create_access_token(data={"sub": agent_user.email})
    agent_headers = {"Authorization": f"Bearer {agent_token}"}

    # 2. Perform Cash Withdrawal
    # Customer withdraws 100.
    # Fee: 1% = 1.0 (from code logic)
    # Total Deducted from Customer: 101.0
    # Customer Wallet: 300 -> 199.0
    # Agent Float: 500 -> 600.0
    # Agent Commission: 100 * 0.02 = 2.0
    
    response = client.post(
        "/agent-transactions/cash-withdrawal",
        json={"user_id": customer.id, "amount": 100.0, "currency": "GHS"},
        headers=agent_headers
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "completed"
    
    # 3. Verify Balances
    db_session.refresh(agent)
    db_session.refresh(customer_wallet)
    
    assert agent.float_balance == 600.0
    assert customer_wallet.balance == 199.0 # 300 - 100 - 1
    assert agent.commission_balance == 2.0

def test_agent_commission_loan_repayment(client, db_session):
    # 1. Setup Data with ACTIVE LOAN
    agent_user = User(email="agent_loan@test.com", password_hash="hash", is_active=True, is_verified=True, is_agent=True)
    db_session.add(agent_user)
    db_session.commit()
    db_session.refresh(agent_user)
    
    agent_wallet = Wallet(user_id=agent_user.id, balance=0.0)
    db_session.add(agent_wallet)
    
    agent = Agent(user_id=agent_user.id, status="active", commission_rate=0.10, float_balance=1000.0, commission_balance=0.0) # 10% commission for easy math
    db_session.add(agent)
    
    # Create Loan
    from backend.models import Loan, LoanApplication
    from datetime import datetime, timedelta
    
    loan_app = LoanApplication(agent_id=agent.id, amount=100.0, repayment_duration=30)
    db_session.add(loan_app)
    db_session.commit()
    
    loan = Loan(
        agent_id=agent.id, 
        application_id=loan_app.id, 
        amount=100.0, 
        outstanding_balance=50.0, # 50 left to pay
        repayment_due_date=datetime.now() + timedelta(days=30)
    )
    db_session.add(loan)
    db_session.commit()
    
    # Create Customer
    customer = User(email="customer_loan@test.com", password_hash="hash", is_active=True, is_verified=True)
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)
    
    customer_wallet = Wallet(user_id=customer.id, balance=0.0)
    db_session.add(customer_wallet)
    db_session.commit()
    
    # Auth
    from backend.core.security import create_access_token
    agent_token = create_access_token(data={"sub": agent_user.email})
    agent_headers = {"Authorization": f"Bearer {agent_token}"}

    # 2. Perform Transaction that earns Commission
    # Deposit 100. Commission 10% = 10.0.
    # Loan Repayment Percentage = 20% (default from config).
    # Repayment Amount = 10.0 * 0.20 = 2.0.
    # Net Commission to Agent Balance = 10.0 - 2.0 = 8.0.
    # Loan Outstanding: 50.0 -> 48.0.
    
    response = client.post(
        "/agent-transactions/cash-deposit",
        json={"user_id": customer.id, "amount": 100.0, "currency": "GHS"},
        headers=agent_headers
    )
    
    assert response.status_code == 201
    
    # 3. Verify
    db_session.refresh(agent)
    db_session.refresh(loan)
    
    assert agent.commission_balance == 8.0 # 10 - 2
    assert loan.outstanding_balance == 48.0 # 50 - 2


def test_agent_startup_loan_float_is_non_withdrawable(client, db_session):
    agent_user = User(email="agent_locked@test.com", password_hash="hash", is_active=True, is_verified=True, is_agent=True)
    db_session.add(agent_user)
    db_session.commit()
    db_session.refresh(agent_user)

    agent_wallet = Wallet(user_id=agent_user.id, balance=0.0)
    db_session.add(agent_wallet)

    agent = Agent(user_id=agent_user.id, status="active", commission_rate=0.02, float_balance=50.0, commission_balance=0.0)
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)

    startup_tx = Transaction(
        user_id=agent_user.id,
        wallet_id=agent_wallet.id,
        agent_id=agent.id,
        type="agent_startup_loan_credit",
        amount=50.0,
        currency="GHS",
        status="completed",
    )
    db_session.add(startup_tx)

    customer = User(email="customer_locked@test.com", password_hash="hash", is_active=True, is_verified=True)
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)

    customer_wallet = Wallet(user_id=customer.id, balance=10.0)
    db_session.add(customer_wallet)
    db_session.commit()

    from backend.core.security import create_access_token

    agent_token = create_access_token(data={"sub": agent_user.email})
    agent_headers = {"Authorization": f"Bearer {agent_token}"}

    response = client.post(
        "/agent-transactions/cash-deposit",
        json={"user_id": customer.id, "amount": 5.0, "currency": "GHS"},
        headers=agent_headers,
    )

    assert response.status_code == 400
    assert "startup loan funds are locked" in response.json()["detail"].lower()
