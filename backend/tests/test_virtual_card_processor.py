from backend.models import Transaction, User, VirtualCard, Wallet
from backend.core.config import settings


def test_processor_authorize_approves_and_deducts_wallet(client, db_session):
    user = User(email="cardproc_ok@test.com", password_hash="hash", is_active=True, is_verified=True)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    wallet = Wallet(user_id=user.id, currency="USD", balance=150.0)
    card = VirtualCard(
        user_id=user.id,
        card_number="4111111111111111",
        expiry_date="12/30",
        cvv_hashed="hashed",
        currency="USD",
        balance=0.0,
        spending_limit=500.0,
        status="active",
        type="rechargeable",
        provider_card_id="prov_card_ok_1",
    )
    db_session.add_all([wallet, card])
    db_session.commit()

    response = client.post(
        "/virtualcards/processor/authorize",
        json={
            "provider_card_id": "prov_card_ok_1",
            "amount": 50.0,
            "currency": "USD",
            "merchant_name": "Amazon",
            "merchant_country": "US",
            "fee": 1.0,
            "fx_margin": 0.5,
            "processor_reference": "AUTH_001",
        },
        headers={"x-card-processor-key": settings.CARD_PROCESSOR_WEBHOOK_KEY},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["approved"] is True
    assert payload["status"] == "approved"
    assert payload["transaction_id"] is not None

    db_session.expire_all()
    updated_wallet = db_session.query(Wallet).filter(Wallet.user_id == user.id).first()
    assert updated_wallet.balance == 98.5

    tx = db_session.query(Transaction).filter(Transaction.id == payload["transaction_id"]).first()
    assert tx is not None
    assert tx.type == "CARD_SPEND"
    assert tx.status == "completed"


def test_processor_authorize_denies_when_insufficient_balance(client, db_session):
    user = User(email="cardproc_low@test.com", password_hash="hash", is_active=True, is_verified=True)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    wallet = Wallet(user_id=user.id, currency="USD", balance=10.0)
    card = VirtualCard(
        user_id=user.id,
        card_number="4222222222222222",
        expiry_date="12/30",
        cvv_hashed="hashed",
        currency="USD",
        balance=0.0,
        spending_limit=500.0,
        status="active",
        type="rechargeable",
        provider_card_id="prov_card_low_1",
    )
    db_session.add_all([wallet, card])
    db_session.commit()

    response = client.post(
        "/virtualcards/processor/authorize",
        json={
            "provider_card_id": "prov_card_low_1",
            "amount": 20.0,
            "currency": "USD",
            "merchant_name": "Netflix",
            "merchant_country": "US",
        },
        headers={"x-card-processor-key": settings.CARD_PROCESSOR_WEBHOOK_KEY},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["approved"] is False
    assert payload["status"] == "denied"
    assert "Insufficient wallet balance" in payload["reason"]

    db_session.expire_all()
    updated_wallet = db_session.query(Wallet).filter(Wallet.user_id == user.id).first()
    assert updated_wallet.balance == 10.0
    tx_count = db_session.query(Transaction).filter(Transaction.user_id == user.id).count()
    assert tx_count == 0


def test_processor_authorize_denies_when_invalid_processor_key(client, db_session):
    response = client.post(
        "/virtualcards/processor/authorize",
        json={
            "provider_card_id": "missing",
            "amount": 10.0,
            "currency": "USD",
            "merchant_name": "Test",
            "merchant_country": "US",
        },
        headers={"x-card-processor-key": "wrong-key"},
    )
    assert response.status_code == 401
