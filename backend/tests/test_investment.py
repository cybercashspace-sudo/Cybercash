import json
from datetime import datetime, timedelta, timezone

from backend.core.security import create_access_token
from backend.core.transaction_types import TransactionType
from backend.database import SessionLocal
from backend.models import Transaction, User, Wallet


def _auth_headers(user_id: int) -> dict:
    token = create_access_token(data={"sub": str(user_id)})
    return {"Authorization": f"Bearer {token}"}


def _build_create_payload(amount: float, duration_days: int, plan_name: str = "Risk-Free Plan") -> dict:
    return {
        "amount": amount,
        "duration_days": duration_days,
        "plan_name": plan_name,
        "expected_rate": 99.0,
        "pin_verified": True,
        "biometric_verified": False,
        "channel": "APP",
        "daily_limit": 1000000.0,
        "biometric_threshold": 2500.0,
        "risk_override": False,
    }


def _build_payout_payload(investment_id: int | None, amount: float = 0.0) -> dict:
    payload = {
        "amount": amount,
        "gain": 0.0,
        "pin_verified": True,
        "biometric_verified": False,
        "channel": "APP",
        "daily_limit": 1000000.0,
        "biometric_threshold": 2500.0,
        "risk_override": False,
    }
    if investment_id is not None:
        payload["investment_id"] = investment_id
    return payload


def _create_user_and_wallet(
    db_session,
    email: str,
    balance: float,
    *,
    is_agent: bool = False,
    phone_number: str | None = None,
    investment_balance: float = 0.0,
):
    user = User(
        email=email,
        phone_number=phone_number,
        password_hash="hash",
        is_active=True,
        is_verified=True,
        is_agent=is_agent,
        role="agent" if is_agent else "user",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    wallet = Wallet(
        user_id=user.id,
        balance=balance,
        investment_balance=investment_balance,
        currency="GHS",
    )
    db_session.add(wallet)
    db_session.commit()
    return user.id


def test_investment_create_rejects_amount_below_minimum(client, db_session):
    user_id = _create_user_and_wallet(db_session, "invest_min@test.com", balance=100.0)
    db_session.close()

    response = client.post(
        "/transactions/investment/create",
        json=_build_create_payload(amount=9.99, duration_days=30),
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 422
    assert "greater than or equal to 10" in str(response.json()).lower()


def test_investment_create_rejects_duration_below_7_days(client, db_session):
    user_id = _create_user_and_wallet(db_session, "invest_duration@test.com", balance=100.0)
    db_session.close()

    response = client.post(
        "/transactions/investment/create",
        json=_build_create_payload(amount=10.0, duration_days=6),
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 422
    assert "greater than or equal to 7" in str(response.json()).lower()


def test_investment_create_rejects_non_standard_duration_period(client, db_session):
    user_id = _create_user_and_wallet(db_session, "invest_duration_standard@test.com", balance=100.0)
    db_session.close()

    response = client.post(
        "/transactions/investment/create",
        json=_build_create_payload(amount=10.0, duration_days=8),
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 400
    assert "choose one of" in response.json()["detail"].lower()
    assert "7, 14, 30, 60, 90, 180, 365" in response.json()["detail"]


def test_user_create_investment_stores_fixed_risk_free_projection(client, db_session):
    user_id = _create_user_and_wallet(db_session, "invest_user_success@test.com", balance=200.0)
    db_session.close()

    response = client.post(
        "/transactions/investment/create",
        json=_build_create_payload(amount=100.0, duration_days=365, plan_name="User Plan"),
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 201
    data = response.json()
    assert data["type"] == TransactionType.INVESTMENT_CREATE
    assert float(data["amount"]) == 100.0

    verify_db = SessionLocal()
    try:
        wallet = verify_db.query(Wallet).filter(Wallet.user_id == user_id).first()
        assert wallet is not None
        assert wallet.balance == 100.0
        assert wallet.investment_balance == 100.0

        tx = verify_db.query(Transaction).filter(Transaction.id == data["id"]).first()
        assert tx is not None
        metadata = json.loads(tx.metadata_json or "{}")
        assert float(metadata.get("expected_rate", 0.0)) == 12.0
        assert float(metadata.get("projected_gross_profit", 0.0)) == 12.0
        assert float(metadata.get("projected_profit_fee", 0.0)) == 1.2
        assert float(metadata.get("projected_net_profit", 0.0)) == 10.8
        assert float(metadata.get("profit_fee_rate", 0.0)) == 0.10
        assert str(metadata.get("investment_status", "")).lower() == "active"
    finally:
        verify_db.close()


def test_agent_can_create_investment_from_main_balance(client, db_session):
    agent_user_id = _create_user_and_wallet(
        db_session,
        "invest_agent_success@test.com",
        balance=50.0,
        is_agent=True,
    )
    db_session.close()

    response = client.post(
        "/transactions/investment/create",
        json=_build_create_payload(amount=10.0, duration_days=30, plan_name="Agent Plan"),
        headers=_auth_headers(agent_user_id),
    )

    assert response.status_code == 201
    data = response.json()
    assert data["type"] == TransactionType.INVESTMENT_CREATE
    assert float(data["amount"]) == 10.0


def test_investment_payout_requires_investment_id(client, db_session):
    user_id = _create_user_and_wallet(db_session, "invest_payout_missing_id@test.com", balance=100.0)
    db_session.close()

    response = client.post(
        "/transactions/investment/payout",
        json=_build_payout_payload(investment_id=None),
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 400
    assert "investment id is required" in response.json()["detail"].lower()


def test_investment_payout_rejects_before_maturity(client, db_session):
    user_id = _create_user_and_wallet(db_session, "invest_not_mature@test.com", balance=120.0)
    db_session.close()

    create_response = client.post(
        "/transactions/investment/create",
        json=_build_create_payload(amount=100.0, duration_days=30, plan_name="Not Mature Yet"),
        headers=_auth_headers(user_id),
    )
    assert create_response.status_code == 201
    investment_id = int(create_response.json()["id"])

    payout_response = client.post(
        "/transactions/investment/payout",
        json=_build_payout_payload(investment_id=investment_id, amount=100.0),
        headers=_auth_headers(user_id),
    )
    assert payout_response.status_code == 400
    assert "not yet mature" in payout_response.json()["detail"].lower()


def test_investment_payout_charges_ten_percent_of_gross_profit(client, db_session):
    user_id = _create_user_and_wallet(db_session, "invest_mature_payout@test.com", balance=150.0)
    db_session.close()

    create_response = client.post(
        "/transactions/investment/create",
        json=_build_create_payload(amount=100.0, duration_days=365, plan_name="Mature Plan"),
        headers=_auth_headers(user_id),
    )
    assert create_response.status_code == 201
    investment_id = int(create_response.json()["id"])

    # Move transaction timestamp back so plan is mature.
    adjust_db = SessionLocal()
    try:
        investment_tx = adjust_db.query(Transaction).filter(Transaction.id == investment_id).first()
        assert investment_tx is not None
        investment_tx.timestamp = datetime.now(timezone.utc) - timedelta(days=366)
        metadata = json.loads(investment_tx.metadata_json or "{}")
        metadata["maturity_at"] = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        investment_tx.metadata_json = json.dumps(metadata)
        adjust_db.add(investment_tx)
        adjust_db.commit()
    finally:
        adjust_db.close()

    payout_response = client.post(
        "/transactions/investment/payout",
        json=_build_payout_payload(investment_id=investment_id, amount=100.0),
        headers=_auth_headers(user_id),
    )
    assert payout_response.status_code == 201
    payout_data = payout_response.json()
    assert payout_data["type"] == TransactionType.INVESTMENT_PAYOUT

    verify_db = SessionLocal()
    try:
        payout_tx = verify_db.query(Transaction).filter(Transaction.id == payout_data["id"]).first()
        assert payout_tx is not None
        payout_metadata = json.loads(payout_tx.metadata_json or "{}")
        assert float(payout_metadata.get("gross_profit", 0.0)) == 12.0
        assert float(payout_metadata.get("fee", 0.0)) == 1.2
        assert float(payout_metadata.get("gain", 0.0)) == 10.8
        assert float(payout_metadata.get("profit_fee_rate", 0.0)) == 0.10
        assert int(payout_metadata.get("investment_id")) == investment_id

        investment_tx = verify_db.query(Transaction).filter(Transaction.id == investment_id).first()
        assert investment_tx is not None
        investment_metadata = json.loads(investment_tx.metadata_json or "{}")
        assert str(investment_metadata.get("investment_status", "")).lower() == "paid_out"

        wallet = verify_db.query(Wallet).filter(Wallet.user_id == user_id).first()
        assert wallet is not None
        assert wallet.balance == 160.8
        assert wallet.investment_balance == 0.0
    finally:
        verify_db.close()


def test_invested_funds_are_locked_from_wallet_transfer_before_claim(client, db_session):
    sender_id = _create_user_and_wallet(
        db_session,
        "invest_lock_sender@test.com",
        balance=80.0,
        investment_balance=60.0,
        phone_number="0240000991",
    )
    recipient_id = _create_user_and_wallet(
        db_session,
        "invest_lock_recipient@test.com",
        balance=5.0,
        phone_number="0240000992",
    )
    db_session.close()

    response = client.post(
        "/wallet/transfer",
        json={
            "recipient_wallet_id": "0240000992",
            "amount": 20.0,
            "currency": "GHS",
            "source_balance": "investment_balance",
            "recipient_must_be_agent": False,
        },
        headers=_auth_headers(sender_id),
    )
    assert response.status_code == 400
    assert "locked" in response.json()["detail"].lower()

    verify_db = SessionLocal()
    try:
        sender_wallet = verify_db.query(Wallet).filter(Wallet.user_id == sender_id).first()
        recipient_wallet = verify_db.query(Wallet).filter(Wallet.user_id == recipient_id).first()
        assert sender_wallet is not None
        assert recipient_wallet is not None
        assert sender_wallet.balance == 80.0
        assert sender_wallet.investment_balance == 60.0
        assert recipient_wallet.balance == 5.0
    finally:
        verify_db.close()
