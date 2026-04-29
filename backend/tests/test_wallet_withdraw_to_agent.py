from backend.core.security import create_access_token
from backend.models import Agent, User, Wallet


def _auth_headers(user_id: int) -> dict:
    token = create_access_token(data={"sub": str(user_id)})
    return {"Authorization": f"Bearer {token}"}


def _create_user_with_wallet(
    db_session,
    *,
    email: str,
    phone_number: str,
    balance: float,
) -> User:
    user = User(
        email=email,
        phone_number=phone_number,
        password_hash="hash",
        is_active=True,
        is_verified=True,
        role="user",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    wallet = Wallet(user_id=user.id, currency="GHS", balance=balance)
    db_session.add(wallet)
    db_session.commit()
    return user


def _set_active_agent(db_session, user: User) -> Agent:
    agent = Agent(user_id=user.id, status="active", commission_rate=0.02)
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent


def test_withdraw_to_agent_rejects_amount_below_one_ghs(client, db_session):
    sender = _create_user_with_wallet(
        db_session,
        email="withdraw_sender_min@test.com",
        phone_number="0241000001",
        balance=20.0,
    )
    recipient = _create_user_with_wallet(
        db_session,
        email="withdraw_agent_min@test.com",
        phone_number="0241000002",
        balance=0.0,
    )
    _set_active_agent(db_session, recipient)

    response = client.post(
        "/wallet/transfer",
        json={
            "recipient_wallet_id": "0241000002",
            "amount": 0.99,
            "currency": "GHS",
            "source_balance": "balance",
            "recipient_must_be_agent": True,
        },
        headers=_auth_headers(sender.id),
    )

    assert response.status_code == 400
    assert "minimum withdrawal amount is ghs 1.00" in response.json()["detail"].lower()


def test_withdraw_to_agent_rejects_non_agent_number(client, db_session):
    sender = _create_user_with_wallet(
        db_session,
        email="withdraw_sender_non_agent@test.com",
        phone_number="0241000011",
        balance=20.0,
    )
    _create_user_with_wallet(
        db_session,
        email="withdraw_non_agent_recipient@test.com",
        phone_number="0241000012",
        balance=0.0,
    )

    response = client.post(
        "/wallet/transfer",
        json={
            "recipient_wallet_id": "0241000012",
            "amount": 5.0,
            "currency": "GHS",
            "source_balance": "balance",
            "recipient_must_be_agent": True,
        },
        headers=_auth_headers(sender.id),
    )

    assert response.status_code == 400
    assert "not an active registered agent" in response.json()["detail"].lower()


def test_withdraw_to_agent_accepts_valid_agent_number_from_one_ghs(client, db_session):
    sender = _create_user_with_wallet(
        db_session,
        email="withdraw_sender_success@test.com",
        phone_number="0241000021",
        balance=20.0,
    )
    recipient = _create_user_with_wallet(
        db_session,
        email="withdraw_agent_success@test.com",
        phone_number="0241000022",
        balance=0.0,
    )
    _set_active_agent(db_session, recipient)

    response = client.post(
        "/wallet/transfer",
        json={
            "recipient_wallet_id": "0241000022",
            "amount": 1.0,
            "currency": "GHS",
            "source_balance": "balance",
            "recipient_must_be_agent": True,
        },
        headers=_auth_headers(sender.id),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["recipient_is_agent"] is True
    assert payload["recipient_wallet_id"] == "0241000022"
    assert float(payload["transfer_fee"]) == 0.01
    assert float(payload["transfer_fee_rate"]) == 0.01
    assert float(payload["total_debited"]) == 1.01

    sender_wallet = db_session.query(Wallet).filter(Wallet.user_id == sender.id).first()
    recipient_wallet = db_session.query(Wallet).filter(Wallet.user_id == recipient.id).first()
    assert sender_wallet is not None
    assert recipient_wallet is not None
    assert float(sender_wallet.balance) == 18.99
    assert float(recipient_wallet.balance) == 1.0
