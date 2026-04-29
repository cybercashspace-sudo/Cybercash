from backend.core.security import create_access_token
from backend.models import User, Wallet


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


def test_p2p_transfer_rejects_amount_below_one_ghs(client, db_session):
    sender = _create_user_with_wallet(
        db_session,
        email="p2p_sender_min@test.com",
        phone_number="0242000001",
        balance=20.0,
    )
    _create_user_with_wallet(
        db_session,
        email="p2p_recipient_min@test.com",
        phone_number="0242000002",
        balance=0.0,
    )

    response = client.post(
        "/wallet/transfer",
        json={
            "recipient_wallet_id": "0242000002",
            "amount": 0.99,
            "currency": "GHS",
            "source_balance": "balance",
            "recipient_must_be_agent": False,
        },
        headers=_auth_headers(sender.id),
    )

    assert response.status_code == 400
    assert "minimum p2p transfer amount is ghs 1.00" in response.json()["detail"].lower()


def test_p2p_transfer_rejects_non_existent_recipient(client, db_session):
    sender = _create_user_with_wallet(
        db_session,
        email="p2p_sender_missing@test.com",
        phone_number="0242000011",
        balance=20.0,
    )

    response = client.post(
        "/wallet/transfer",
        json={
            "recipient_wallet_id": "0242999999",
            "amount": 5.0,
            "currency": "GHS",
            "source_balance": "balance",
            "recipient_must_be_agent": False,
        },
        headers=_auth_headers(sender.id),
    )

    assert response.status_code == 404
    assert "recipient user not found" in response.json()["detail"].lower()


def test_p2p_transfer_is_free_under_daily_limit(client, db_session):
    sender = _create_user_with_wallet(
        db_session,
        email="p2p_sender_success@test.com",
        phone_number="0242000021",
        balance=200.0,
    )
    recipient = _create_user_with_wallet(
        db_session,
        email="p2p_recipient_success@test.com",
        phone_number="0242000022",
        balance=0.0,
    )

    response = client.post(
        "/wallet/transfer",
        json={
            "recipient_wallet_id": "0242000022",
            "amount": 10.0,
            "currency": "GHS",
            "source_balance": "balance",
            "recipient_must_be_agent": False,
        },
        headers=_auth_headers(sender.id),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["recipient_is_agent"] is False
    assert payload["recipient_wallet_id"] == "0242000022"
    assert float(payload["transfer_fee"]) == 0.0
    assert float(payload["transfer_fee_rate"]) == 0.005
    assert float(payload["total_debited"]) == 10.0
    assert float(payload["p2p_daily_free_limit"]) == 100.0
    assert float(payload["p2p_total_sent_today_before"]) == 0.0
    assert float(payload["p2p_free_remaining_before"]) == 100.0
    assert float(payload["p2p_fee_free_amount"]) == 10.0
    assert float(payload["p2p_feeable_amount"]) == 0.0

    sender_wallet = db_session.query(Wallet).filter(Wallet.user_id == sender.id).first()
    recipient_wallet = db_session.query(Wallet).filter(Wallet.user_id == recipient.id).first()
    assert sender_wallet is not None
    assert recipient_wallet is not None
    assert float(sender_wallet.balance) == 190.0
    assert float(recipient_wallet.balance) == 10.0


def test_p2p_transfer_charges_fee_only_above_daily_free_limit(client, db_session):
    sender = _create_user_with_wallet(
        db_session,
        email="p2p_sender_over_limit@test.com",
        phone_number="0242000031",
        balance=200.0,
    )
    recipient = _create_user_with_wallet(
        db_session,
        email="p2p_recipient_over_limit@test.com",
        phone_number="0242000032",
        balance=0.0,
    )

    first = client.post(
        "/wallet/transfer",
        json={
            "recipient_wallet_id": "0242000032",
            "amount": 90.0,
            "currency": "GHS",
            "source_balance": "balance",
            "recipient_must_be_agent": False,
        },
        headers=_auth_headers(sender.id),
    )
    assert first.status_code == 200
    assert float(first.json()["transfer_fee"]) == 0.0

    second = client.post(
        "/wallet/transfer",
        json={
            "recipient_wallet_id": "0242000032",
            "amount": 20.0,
            "currency": "GHS",
            "source_balance": "balance",
            "recipient_must_be_agent": False,
        },
        headers=_auth_headers(sender.id),
    )

    assert second.status_code == 200
    payload = second.json()
    assert float(payload["transfer_fee"]) == 0.05
    assert float(payload["transfer_fee_rate"]) == 0.005
    assert float(payload["total_debited"]) == 20.05
    assert float(payload["p2p_total_sent_today_before"]) == 90.0
    assert float(payload["p2p_free_remaining_before"]) == 10.0
    assert float(payload["p2p_fee_free_amount"]) == 10.0
    assert float(payload["p2p_feeable_amount"]) == 10.0

    sender_wallet = db_session.query(Wallet).filter(Wallet.user_id == sender.id).first()
    recipient_wallet = db_session.query(Wallet).filter(Wallet.user_id == recipient.id).first()
    assert float(sender_wallet.balance) == 89.95
    assert float(recipient_wallet.balance) == 110.0
