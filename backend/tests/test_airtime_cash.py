from backend.core.security import create_access_token
from backend.models import AirtimeCashSale, User


def test_authenticated_user_can_generate_a_persisted_airtime_cash_number(client, db_session):
    user = User(
        email="airtime-cash-user@example.com",
        password_hash="test-hash",
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    headers = {"Authorization": f"Bearer {create_access_token(data={'sub': user.email})}"}

    response = client.post(
        "/api/airtime/cash/quote",
        json={"phone": "0241234567", "network": "MTN", "amount": 20, "currency": "GHS"},
        headers=headers,
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["sale_id"]
    assert payload["merchant_number"]
    assert payload["status"] == "pending"
    assert db_session.query(AirtimeCashSale).filter_by(id=payload["sale_id"], user_id=user.id).count() == 1


def test_airtime_cash_quote_rejects_invalid_phone_without_creating_a_sale(client, db_session):
    user = User(
        email="airtime-cash-invalid@example.com",
        password_hash="test-hash",
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    headers = {"Authorization": f"Bearer {create_access_token(data={'sub': user.email})}"}

    response = client.post(
        "/api/airtime/cash/quote",
        json={"phone": "123", "network": "MTN", "amount": 20, "currency": "GHS"},
        headers=headers,
    )

    assert response.status_code == 422
    assert db_session.query(AirtimeCashSale).filter_by(user_id=user.id).count() == 0
