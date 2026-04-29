import json

from backend.core.security import create_access_token
from backend.models import Agent, Transaction, User, Wallet


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(data={"sub": user.email})
    return {"Authorization": f"Bearer {token}"}


def test_virtual_card_creation_charges_user_ghs_25(client, db_session):
    user = User(
        email="card_fee_user@test.com",
        password_hash="hash",
        is_active=True,
        is_verified=True,
        status="active",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    wallet = Wallet(user_id=user.id, currency="GHS", balance=100.0)
    db_session.add(wallet)
    db_session.commit()

    response = client.post(
        "/virtualcards/request",
        json={"currency": "USD", "type": "rechargeable", "spending_limit": 0},
        headers=_auth_headers(user),
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["issuance_fee_paid"] == 25.0

    db_session.expire_all()
    updated_wallet = db_session.query(Wallet).filter(Wallet.user_id == user.id).first()
    assert updated_wallet.balance == 75.0

    fee_tx = db_session.query(Transaction).filter(Transaction.user_id == user.id).order_by(Transaction.id.desc()).first()
    assert fee_tx is not None
    assert fee_tx.type == "VIRTUAL_CARD_ISSUANCE_FEE"
    assert fee_tx.amount == 25.0
    assert fee_tx.currency == "GHS"

    metadata = json.loads(fee_tx.metadata_json or "{}")
    assert metadata["virtual_card_id"] == payload["id"]
    assert metadata["creation_fee_ghs"] == 25.0


def test_virtual_card_creation_charges_agent_ghs_25(client, db_session):
    user = User(
        email="card_fee_agent@test.com",
        password_hash="hash",
        is_active=True,
        is_verified=True,
        is_agent=True,
        role="agent",
        status="active",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    agent = Agent(user_id=user.id, status="active", commission_rate=0.02, float_balance=0.0)
    wallet = Wallet(user_id=user.id, currency="GHS", balance=80.0)
    db_session.add_all([agent, wallet])
    db_session.commit()

    response = client.post(
        "/virtualcards/request",
        json={"currency": "USD", "type": "one-time", "spending_limit": 50},
        headers=_auth_headers(user),
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["issuance_fee_paid"] == 25.0

    db_session.expire_all()
    updated_wallet = db_session.query(Wallet).filter(Wallet.user_id == user.id).first()
    assert updated_wallet.balance == 55.0

    fee_tx = db_session.query(Transaction).filter(Transaction.user_id == user.id).order_by(Transaction.id.desc()).first()
    assert fee_tx is not None
    assert fee_tx.type == "VIRTUAL_CARD_ISSUANCE_FEE"
    assert fee_tx.amount == 25.0
    assert fee_tx.currency == "GHS"

