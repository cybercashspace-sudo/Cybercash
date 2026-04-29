from backend.models import Agent, Transaction, User, Wallet
from backend.core.security import create_access_token
from backend.core.transaction_types import TransactionType


def _agent_headers(agent_email: str) -> dict:
    token = create_access_token(data={"sub": agent_email})
    return {"Authorization": f"Bearer {token}"}


def test_agent_cash_deposit_by_customer_email(client, db_session):
    agent_user = User(email="agent_email_lookup@test.com", password_hash="hash", is_active=True, is_verified=True, is_agent=True)
    customer = User(email="customer_lookup@test.com", password_hash="hash", is_active=True, is_verified=True)
    db_session.add_all([agent_user, customer])
    db_session.commit()
    db_session.refresh(agent_user)
    db_session.refresh(customer)

    db_session.add(Wallet(user_id=agent_user.id, balance=0.0))
    customer_wallet = Wallet(user_id=customer.id, balance=20.0)
    db_session.add(customer_wallet)
    db_session.add(Agent(user_id=agent_user.id, status="active", commission_rate=0.02, float_balance=1000.0, commission_balance=0.0))
    db_session.commit()

    response = client.post(
        "/agent-transactions/cash-deposit",
        json={"customer_email": customer.email, "amount": 100.0, "currency": "GHS"},
        headers=_agent_headers(agent_user.email),
    )
    assert response.status_code == 201

    db_session.expire_all()
    updated_customer_wallet = db_session.query(Wallet).filter(Wallet.user_id == customer.id).first()
    assert updated_customer_wallet.balance == 120.0


def test_agent_cash_withdrawal_by_customer_phone(client, db_session):
    agent_user = User(email="agent_phone_lookup@test.com", password_hash="hash", is_active=True, is_verified=True, is_agent=True)
    customer = User(email="customer_phone_lookup@test.com", phone_number="0241234567", password_hash="hash", is_active=True, is_verified=True)
    db_session.add_all([agent_user, customer])
    db_session.commit()
    db_session.refresh(agent_user)
    db_session.refresh(customer)

    db_session.add(Wallet(user_id=agent_user.id, balance=0.0))
    customer_wallet = Wallet(user_id=customer.id, balance=300.0)
    db_session.add(customer_wallet)
    db_session.add(Agent(user_id=agent_user.id, status="active", commission_rate=0.02, float_balance=500.0, commission_balance=0.0))
    db_session.commit()

    response = client.post(
        "/agent-transactions/cash-withdrawal",
        json={"customer_phone": customer.phone_number, "amount": 100.0, "currency": "GHS"},
        headers=_agent_headers(agent_user.email),
    )
    assert response.status_code == 201

    db_session.expire_all()
    updated_customer_wallet = db_session.query(Wallet).filter(Wallet.user_id == customer.id).first()
    assert updated_customer_wallet.balance == 199.0


def test_agent_wallet_structure_and_history(client, db_session):
    agent_user = User(email="agent_structure@test.com", password_hash="hash", is_active=True, is_verified=True, is_agent=True)
    customer = User(email="customer_structure@test.com", password_hash="hash", is_active=True, is_verified=True)
    db_session.add_all([agent_user, customer])
    db_session.commit()
    db_session.refresh(agent_user)
    db_session.refresh(customer)

    db_session.add(Wallet(user_id=agent_user.id, balance=0.0))
    db_session.add(Wallet(user_id=customer.id, balance=200.0))
    db_session.add(Agent(user_id=agent_user.id, status="active", commission_rate=0.02, float_balance=600.0, commission_balance=0.0))
    db_session.commit()

    headers = _agent_headers(agent_user.email)
    resp = client.post(
        "/agent-transactions/cash-withdrawal",
        json={"customer_email": customer.email, "amount": 50.0, "currency": "GHS"},
        headers=headers,
    )
    assert resp.status_code == 201

    summary = client.get("/agent-transactions/me/wallet-structure", headers=headers)
    assert summary.status_code == 200
    summary_data = summary.json()
    assert "agent_float_balance" in summary_data
    assert "agent_commission_balance" in summary_data
    assert summary_data["agent_transaction_count"] >= 1

    history = client.get("/agent-transactions/me/history", headers=headers)
    assert history.status_code == 200
    history_data = history.json()
    assert isinstance(history_data, list)
    assert len(history_data) >= 1


def test_agent_history_and_recovery_candidates_normalize_null_commission(client, db_session):
    agent_user = User(email="agent_null_commission@test.com", password_hash="hash", is_active=True, is_verified=True, is_agent=True)
    customer = User(email="customer_null_commission@test.com", password_hash="hash", is_active=True, is_verified=True)
    db_session.add_all([agent_user, customer])
    db_session.commit()
    db_session.refresh(agent_user)
    db_session.refresh(customer)

    agent_wallet = Wallet(user_id=agent_user.id, balance=0.0)
    customer_wallet = Wallet(user_id=customer.id, balance=150.0)
    db_session.add_all([agent_wallet, customer_wallet])
    db_session.commit()
    db_session.refresh(customer_wallet)

    agent = Agent(
        user_id=agent_user.id,
        status="active",
        commission_rate=0.02,
        float_balance=500.0,
        commission_balance=0.0,
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)

    legacy_completed = Transaction(
        user_id=customer.id,
        wallet_id=customer_wallet.id,
        type=TransactionType.AGENT_DEPOSIT,
        amount=40.0,
        currency="GHS",
        agent_id=agent.id,
        commission_earned=None,
        status="completed",
    )
    legacy_failed = Transaction(
        user_id=customer.id,
        wallet_id=customer_wallet.id,
        type=TransactionType.AGENT_WITHDRAWAL,
        amount=20.0,
        currency="GHS",
        agent_id=agent.id,
        commission_earned=None,
        status="failed",
    )
    db_session.add_all([legacy_completed, legacy_failed])
    db_session.commit()

    headers = _agent_headers(agent_user.email)

    history = client.get("/agent-transactions/me/history", headers=headers)
    assert history.status_code == 200
    history_data = history.json()
    assert len(history_data) == 2
    assert all(row["commission_earned"] == 0.0 for row in history_data)

    recovery = client.get("/agent-transactions/me/recovery-candidates", headers=headers)
    assert recovery.status_code == 200
    recovery_data = recovery.json()
    assert len(recovery_data) == 1
    assert recovery_data[0]["status"] == "failed"
    assert recovery_data[0]["commission_earned"] == 0.0
