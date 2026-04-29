from unittest.mock import AsyncMock, patch

from backend.models import Transaction, User, Wallet


def test_airtime_purchase_success(client, db_session):
    user = User(email="airtime_success@test.com", password_hash="hash", is_active=True, is_verified=True)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    wallet = Wallet(user_id=user.id, balance=100.0, currency="GHS")
    db_session.add(wallet)
    db_session.commit()

    from backend.core.security import create_access_token

    token = create_access_token(data={"sub": str(user.id)})
    headers = {"Authorization": f"Bearer {token}"}

    with patch(
        "backend.routes.airtime.momo_service.initiate_airtime_payment",
        new=AsyncMock(
            return_value={
                "status": "successful",
                "message": "Airtime purchase successful.",
                "processor_transaction_id": "MOMO_AIRTIME_OK",
            }
        ),
    ), patch(
        "backend.routes.airtime.notification_service.send_sms",
        new=AsyncMock(return_value=True),
    ) as sms_mock:
        response = client.post(
            "/api/airtime/purchase",
            json={"network": "MTN", "phone": "0240000000", "amount": 20.0},
            headers=headers,
        )

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "completed"
    assert data["type"] == "AIRTIME"

    db_session.refresh(wallet)
    assert wallet.balance == 80.0

    tx = db_session.query(Transaction).filter(Transaction.user_id == user.id).first()
    assert tx is not None
    assert tx.status == "completed"
    assert tx.provider == "momo"
    sms_mock.assert_awaited()


def test_airtime_purchase_provider_failure_refunds_wallet(client, db_session):
    user = User(email="airtime_fail@test.com", password_hash="hash", is_active=True, is_verified=True)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    wallet = Wallet(user_id=user.id, balance=100.0, currency="GHS")
    db_session.add(wallet)
    db_session.commit()

    from backend.core.security import create_access_token

    token = create_access_token(data={"sub": str(user.id)})
    headers = {"Authorization": f"Bearer {token}"}

    with patch(
        "backend.routes.airtime.momo_service.initiate_airtime_payment",
        new=AsyncMock(return_value={"status": "failed", "message": "Provider down"}),
    ):
        response = client.post(
            "/api/airtime/purchase",
            json={"network": "VODAFONE", "phone": "0201111111", "amount": 20.0},
            headers=headers,
        )

    assert response.status_code == 502
    db_session.refresh(wallet)
    assert wallet.balance == 100.0

    tx = db_session.query(Transaction).filter(Transaction.user_id == user.id).first()
    assert tx is not None
    assert tx.status == "failed"


def test_airtime_purchase_insufficient_balance(client, db_session):
    user = User(email="airtime_low@test.com", password_hash="hash", is_active=True, is_verified=True)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    wallet = Wallet(user_id=user.id, balance=5.0, currency="GHS")
    db_session.add(wallet)
    db_session.commit()

    from backend.core.security import create_access_token

    token = create_access_token(data={"sub": str(user.id)})
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        "/api/airtime/purchase",
        json={"network": "AirtelTigo", "phone": "0272222222", "amount": 20.0},
        headers=headers,
    )
    assert response.status_code == 400
    assert "Insufficient wallet balance" in response.json()["detail"]


def test_airtime_purchase_rejects_amount_below_one_ghs(client, db_session):
    user = User(email="airtime_min@test.com", password_hash="hash", is_active=True, is_verified=True)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    wallet = Wallet(user_id=user.id, balance=10.0, currency="GHS")
    db_session.add(wallet)
    db_session.commit()

    from backend.core.security import create_access_token

    token = create_access_token(data={"sub": str(user.id)})
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        "/api/airtime/purchase",
        json={"network": "MTN", "phone": "0240000000", "amount": 0.5},
        headers=headers,
    )

    assert response.status_code == 422
