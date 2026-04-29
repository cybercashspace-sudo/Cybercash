import json

from backend.database import SessionLocal
from backend.core.security import create_access_token
from backend.core.transaction_types import TransactionType
from backend.models import Transaction, User, Wallet


def _auth_headers(user_id: int) -> dict:
    token = create_access_token(data={"sub": str(user_id)})
    return {"Authorization": f"Bearer {token}"}


def _build_escrow_payload(amount: float, recipient_wallet_id: str, fee: float = 0.0) -> dict:
    return {
        "amount": amount,
        "recipient_wallet_id": recipient_wallet_id,
        "fee": fee,
        "description": "Test escrow deal",
        "pin_verified": True,
        "biometric_verified": False,
        "channel": "APP",
        "daily_limit": 100000.0,
        "biometric_threshold": 2500.0,
        "risk_override": False,
    }


def _build_release_payload(
    amount: float,
    recipient_user_id: int | None = None,
    fee: float = 0.0,
    escrow_deal_id: int | None = None,
) -> dict:
    payload = {
        "amount": amount,
        "fee": fee,
        "release_note": "Release test",
        "pin_verified": True,
        "biometric_verified": True,
        "channel": "APP",
        "daily_limit": 100000.0,
        "biometric_threshold": 2500.0,
        "risk_override": False,
    }
    if recipient_user_id is not None:
        payload["recipient_user_id"] = recipient_user_id
    if escrow_deal_id is not None:
        payload["escrow_deal_id"] = escrow_deal_id
    return payload


def test_escrow_create_charges_fixed_ghs5_fee(client, db_session):
    sender = User(
        email="escrow_sender@test.com",
        momo_number="0243000001",
        phone_number="0243000001",
        password_hash="hash",
        is_active=True,
        is_verified=True,
    )
    recipient = User(
        email="escrow_recipient@test.com",
        momo_number="0243000002",
        phone_number="0243000002",
        password_hash="hash",
        is_active=True,
        is_verified=True,
    )
    db_session.add_all([sender, recipient])
    db_session.commit()
    db_session.refresh(sender)
    db_session.refresh(recipient)

    sender_wallet = Wallet(user_id=sender.id, balance=100.0, escrow_balance=0.0, currency="GHS")
    recipient_wallet = Wallet(user_id=recipient.id, balance=5.0, escrow_balance=0.0, currency="GHS")
    db_session.add_all([sender_wallet, recipient_wallet])
    db_session.commit()
    sender_id = sender.id
    recipient_id = recipient.id
    db_session.close()

    response = client.post(
        "/transactions/escrow/create",
        json=_build_escrow_payload(amount=20.0, recipient_wallet_id=recipient.momo_number or "", fee=0.0),
        headers=_auth_headers(sender_id),
    )

    assert response.status_code == 201
    data = response.json()
    assert data["type"] == TransactionType.ESCROW_CREATE
    assert data["amount"] == 20.0

    verify_db = SessionLocal()
    try:
        updated_sender_wallet = verify_db.query(Wallet).filter(Wallet.user_id == sender_id).first()
        assert updated_sender_wallet is not None
        assert updated_sender_wallet.balance == 75.0
        assert updated_sender_wallet.escrow_balance == 20.0

        created_tx = verify_db.query(Transaction).filter(Transaction.id == data["id"]).first()
        assert created_tx is not None
        metadata = json.loads(created_tx.metadata_json or "{}")
        assert float(metadata.get("fee", 0.0)) == 5.0
        assert metadata.get("recipient_id") == recipient_id
        assert metadata.get("recipient_wallet_id") == "0243000002"
    finally:
        verify_db.close()


def test_escrow_create_rejects_self_recipient(client, db_session):
    sender = User(
        email="escrow_self@test.com",
        momo_number="0243000010",
        phone_number="0243000010",
        password_hash="hash",
        is_active=True,
        is_verified=True,
    )
    db_session.add(sender)
    db_session.commit()
    db_session.refresh(sender)

    sender_wallet = Wallet(user_id=sender.id, balance=100.0, escrow_balance=0.0, currency="GHS")
    db_session.add(sender_wallet)
    db_session.commit()
    sender_id = sender.id
    db_session.close()

    response = client.post(
        "/transactions/escrow/create",
        json=_build_escrow_payload(amount=20.0, recipient_wallet_id=sender.momo_number or "", fee=0.0),
        headers=_auth_headers(sender_id),
    )

    assert response.status_code == 400
    assert "different user" in response.json()["detail"].lower()


def test_escrow_create_fee_cannot_be_bypassed_with_zero_fee_payload(client, db_session):
    sender = User(
        email="escrow_strict_sender@test.com",
        momo_number="0243000021",
        phone_number="0243000021",
        password_hash="hash",
        is_active=True,
        is_verified=True,
    )
    recipient = User(
        email="escrow_strict_recipient@test.com",
        momo_number="0243000022",
        phone_number="0243000022",
        password_hash="hash",
        is_active=True,
        is_verified=True,
    )
    db_session.add_all([sender, recipient])
    db_session.commit()
    db_session.refresh(sender)
    db_session.refresh(recipient)

    sender_wallet = Wallet(user_id=sender.id, balance=30.0, escrow_balance=0.0, currency="GHS")
    recipient_wallet = Wallet(user_id=recipient.id, balance=0.0, escrow_balance=0.0, currency="GHS")
    db_session.add_all([sender_wallet, recipient_wallet])
    db_session.commit()
    sender_id = sender.id
    recipient_id = recipient.id
    db_session.close()

    response = client.post(
        "/transactions/escrow/create",
        json=_build_escrow_payload(amount=30.0, recipient_wallet_id=recipient.momo_number or "", fee=0.0),
        headers=_auth_headers(sender_id),
    )

    assert response.status_code == 400
    assert "insufficient available balance" in response.json()["detail"].lower()


def test_escrow_create_rejects_amount_below_ghs20(client, db_session):
    sender = User(
        email="escrow_amount_sender@test.com",
        momo_number="0243000031",
        phone_number="0243000031",
        password_hash="hash",
        is_active=True,
        is_verified=True,
    )
    recipient = User(
        email="escrow_amount_recipient@test.com",
        momo_number="0243000032",
        phone_number="0243000032",
        password_hash="hash",
        is_active=True,
        is_verified=True,
    )
    db_session.add_all([sender, recipient])
    db_session.commit()
    db_session.refresh(sender)
    db_session.refresh(recipient)

    sender_wallet = Wallet(user_id=sender.id, balance=100.0, escrow_balance=0.0, currency="GHS")
    recipient_wallet = Wallet(user_id=recipient.id, balance=0.0, escrow_balance=0.0, currency="GHS")
    db_session.add_all([sender_wallet, recipient_wallet])
    db_session.commit()
    sender_id = sender.id
    recipient_number = recipient.momo_number or ""
    db_session.close()

    response = client.post(
        "/transactions/escrow/create",
        json=_build_escrow_payload(amount=19.99, recipient_wallet_id=recipient_number, fee=0.0),
        headers=_auth_headers(sender_id),
    )

    assert response.status_code == 400
    assert "minimum escrow deal amount is ghs 20.00" in response.json()["detail"].lower()


def test_escrow_create_rejects_unregistered_number(client, db_session):
    sender = User(
        email="escrow_bad_number_sender@test.com",
        momo_number="0243000041",
        phone_number="0243000041",
        password_hash="hash",
        is_active=True,
        is_verified=True,
    )
    db_session.add(sender)
    db_session.commit()
    db_session.refresh(sender)

    sender_wallet = Wallet(user_id=sender.id, balance=200.0, escrow_balance=0.0, currency="GHS")
    db_session.add(sender_wallet)
    db_session.commit()
    sender_id = sender.id
    db_session.close()

    response = client.post(
        "/transactions/escrow/create",
        json=_build_escrow_payload(amount=20.0, recipient_wallet_id="0243999999", fee=0.0),
        headers=_auth_headers(sender_id),
    )

    assert response.status_code == 400
    assert "recipient not found" in response.json()["detail"].lower()


def test_escrow_release_deal_charges_receiver_fixed_ghs5_fee(client, db_session):
    sender = User(
        email="escrow_release_sender@test.com",
        momo_number="0243000051",
        phone_number="0243000051",
        password_hash="hash",
        is_active=True,
        is_verified=True,
    )
    recipient = User(
        email="escrow_release_recipient@test.com",
        momo_number="0243000052",
        phone_number="0243000052",
        password_hash="hash",
        is_active=True,
        is_verified=True,
    )
    db_session.add_all([sender, recipient])
    db_session.commit()
    db_session.refresh(sender)
    db_session.refresh(recipient)

    sender_wallet = Wallet(user_id=sender.id, balance=120.0, escrow_balance=0.0, currency="GHS")
    recipient_wallet = Wallet(user_id=recipient.id, balance=1.0, escrow_balance=0.0, currency="GHS")
    db_session.add_all([sender_wallet, recipient_wallet])
    db_session.commit()
    sender_id = sender.id
    recipient_id = recipient.id
    db_session.close()

    create_response = client.post(
        "/transactions/escrow/create",
        json=_build_escrow_payload(amount=20.0, recipient_wallet_id=recipient.momo_number or "", fee=0.0),
        headers=_auth_headers(sender_id),
    )
    assert create_response.status_code == 201
    deal_id = int(create_response.json()["id"])

    release_response = client.post(
        f"/transactions/escrow/{deal_id}/release",
        headers=_auth_headers(sender_id),
    )
    assert release_response.status_code == 201
    assert release_response.json()["type"] == TransactionType.ESCROW_RELEASE

    verify_db = SessionLocal()
    try:
        updated_sender_wallet = verify_db.query(Wallet).filter(Wallet.user_id == sender_id).first()
        updated_recipient_wallet = verify_db.query(Wallet).filter(Wallet.user_id == recipient_id).first()
        assert updated_sender_wallet is not None
        assert updated_recipient_wallet is not None
        assert updated_sender_wallet.balance == 95.0
        assert updated_sender_wallet.escrow_balance == 0.0
        assert updated_recipient_wallet.balance == 16.0

        release_tx = (
            verify_db.query(Transaction)
            .filter(
                Transaction.user_id == sender_id,
                Transaction.type == TransactionType.ESCROW_RELEASE,
            )
            .order_by(Transaction.id.desc())
            .first()
        )
        assert release_tx is not None
        release_metadata = json.loads(release_tx.metadata_json or "{}")
        assert float(release_metadata.get("fee", 0.0)) == 5.0
        assert int(release_metadata.get("recipient_id")) == recipient_id
        assert int(release_metadata.get("escrow_deal_id")) == deal_id
        assert str(release_metadata.get("recipient_wallet_id")) == "0243000052"
    finally:
        verify_db.close()


def test_escrow_release_requires_deal_reference(client, db_session):
    sender = User(
        email="escrow_release_no_deal_sender@test.com",
        momo_number="0243000061",
        phone_number="0243000061",
        password_hash="hash",
        is_active=True,
        is_verified=True,
    )
    recipient = User(
        email="escrow_release_no_deal_recipient@test.com",
        momo_number="0243000062",
        phone_number="0243000062",
        password_hash="hash",
        is_active=True,
        is_verified=True,
    )
    db_session.add_all([sender, recipient])
    db_session.commit()
    db_session.refresh(sender)
    db_session.refresh(recipient)

    sender_wallet = Wallet(user_id=sender.id, balance=120.0, escrow_balance=20.0, currency="GHS")
    recipient_wallet = Wallet(user_id=recipient.id, balance=1.0, escrow_balance=0.0, currency="GHS")
    db_session.add_all([sender_wallet, recipient_wallet])
    db_session.commit()
    sender_id = sender.id
    recipient_id = recipient.id
    db_session.close()

    release_response = client.post(
        "/transactions/escrow/release",
        json=_build_release_payload(amount=20.0, fee=0.0),
        headers=_auth_headers(sender_id),
    )
    assert release_response.status_code == 400
    assert "deal id is required" in release_response.json()["detail"].lower()

    verify_db = SessionLocal()
    try:
        updated_sender_wallet = verify_db.query(Wallet).filter(Wallet.user_id == sender_id).first()
        updated_recipient_wallet = verify_db.query(Wallet).filter(Wallet.user_id == recipient_id).first()
        assert updated_sender_wallet is not None
        assert updated_recipient_wallet is not None
        assert updated_sender_wallet.escrow_balance == 20.0
        assert updated_recipient_wallet.balance == 1.0
    finally:
        verify_db.close()
