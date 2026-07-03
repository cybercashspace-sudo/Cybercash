import asyncio
from datetime import datetime, timedelta, timezone

from backend.core.security import create_jwt
from backend.core.transaction_types import TransactionType
from backend.database import async_session
from backend.models import Transaction, User, Wallet
from backend.services.reconciliation_service import repair_wallet_balance
from utils.security import hash_pin


def _create_returning_user(db_session, *, momo_number: str, balance: float) -> User:
    pin_hash = hash_pin("1234")
    user = User(
        momo_number=momo_number,
        phone_number=momo_number,
        full_name="Returning User",
        provider="MTN",
        pin_hash=pin_hash,
        password_hash=pin_hash,
        is_verified=True,
        is_agent=False,
        role="user",
        status="active",
        token_version=0,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    wallet = Wallet(user_id=user.id, currency="GHS", balance=balance)
    db_session.add(wallet)
    db_session.commit()
    db_session.refresh(wallet)

    return user


def _add_partial_completed_ledger(db_session, user: User, *, amount: float) -> None:
    wallet = db_session.query(Wallet).filter(Wallet.user_id == user.id).first()
    tx = Transaction(
        user_id=user.id,
        wallet_id=wallet.id,
        type=TransactionType.FUNDING,
        entry_type="credit",
        amount=amount,
        currency=wallet.currency or "GHS",
        status="completed",
    )
    db_session.add(tx)
    db_session.commit()


def test_login_does_not_reduce_wallet_to_partial_ledger(client, db_session):
    user = _create_returning_user(db_session, momo_number="0247999002", balance=275.50)
    _add_partial_completed_ledger(db_session, user, amount=50.00)

    response = client.post(
        "/auth/login",
        json={"momo_number": user.momo_number, "pin": "1234", "device_id": "returning-device"},
    )

    assert response.status_code == 200
    db_session.expire_all()
    wallet = db_session.query(Wallet).filter(Wallet.user_id == user.id).first()
    assert float(wallet.balance) == 275.50


def test_wallet_me_does_not_reduce_realtime_balance_to_partial_ledger(client, db_session):
    user = _create_returning_user(db_session, momo_number="0247999003", balance=425.25)
    _add_partial_completed_ledger(db_session, user, amount=25.00)
    token = create_jwt(user.id, token_version=0)

    response = client.get("/wallet/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    db_session.expire_all()
    wallet = db_session.query(Wallet).filter(Wallet.user_id == user.id).first()
    assert float(wallet.balance) == 425.25


def test_repair_refuses_to_reduce_realtime_balance_to_partial_ledger(db_session):
    user = _create_returning_user(db_session, momo_number="0247999005", balance=650.00)
    _add_partial_completed_ledger(db_session, user, amount=75.00)

    async def _run_repair():
        async with async_session() as session:
            return await repair_wallet_balance(session, user.id, admin_id=1)

    success, details = asyncio.run(_run_repair())

    assert success is False
    assert details["reason"] == "ledger_balance_would_reduce_wallet_balance"

    db_session.expire_all()
    wallet = db_session.query(Wallet).filter(Wallet.user_id == user.id).first()
    assert float(wallet.balance) == 650.00


def test_ten_year_absence_with_empty_ledger_preserves_wallet_balance_on_login_and_read(client, db_session):
    user = _create_returning_user(db_session, momo_number="0247999004", balance=918.75)
    ten_years_ago = datetime.now(timezone.utc) - timedelta(days=365 * 10)

    user.created_at = ten_years_ago
    wallet = db_session.query(Wallet).filter(Wallet.user_id == user.id).first()
    wallet.created_at = ten_years_ago
    wallet.updated_at = ten_years_ago
    wallet.last_verified_at = ten_years_ago
    wallet.last_synced_with_ledger = ten_years_ago
    db_session.add(user)
    db_session.add(wallet)
    db_session.commit()

    login_response = client.post(
        "/auth/login",
        json={"momo_number": user.momo_number, "pin": "1234", "device_id": "returning-device"},
    )
    assert login_response.status_code == 200

    token = login_response.json()["access_token"]
    wallet_response = client.get("/wallet/me", headers={"Authorization": f"Bearer {token}"})
    assert wallet_response.status_code == 200
    assert float(wallet_response.json()["balance"]) == 918.75

    db_session.expire_all()
    preserved_wallet = db_session.query(Wallet).filter(Wallet.user_id == user.id).first()
    assert float(preserved_wallet.balance) == 918.75
