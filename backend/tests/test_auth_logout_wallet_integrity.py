from backend.core.security import create_jwt
from backend.models import User, Wallet
from utils.security import hash_pin


def test_logout_preserves_user_wallet_balance(client, db_session):
    pin_hash = hash_pin("1234")
    user = User(
        momo_number="0247999001",
        phone_number="0247999001",
        full_name="Ama Wallet",
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

    wallet = Wallet(user_id=user.id, currency="GHS", balance=275.50)
    db_session.add(wallet)
    db_session.commit()

    token = create_jwt(user.id, token_version=0)
    response = client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200

    db_session.expire_all()
    preserved_wallet = db_session.query(Wallet).filter(Wallet.user_id == user.id).first()
    preserved_user = db_session.query(User).filter(User.id == user.id).first()

    assert preserved_wallet is not None
    assert float(preserved_wallet.balance) == 275.50
    assert preserved_user is not None
    assert int(preserved_user.token_version) == 1
