from unittest.mock import AsyncMock, patch

from backend.main import app
from backend.dependencies.auth import get_current_user
from backend.models import CryptoTransaction, CryptoWallet, User


def override_get_current_user_btc():
    return User(
        id=600,
        email="btc_test@example.com",
        full_name="BTC Test",
        is_active=True,
        is_verified=True,
    )


def test_btc_withdrawal_deducts_and_saves_tx_hash(client, db_session):
    app.dependency_overrides[get_current_user] = override_get_current_user_btc
    try:
        user = User(
            id=600,
            email="btc_test@example.com",
            full_name="BTC Test",
            password_hash="hash",
            is_active=True,
            is_verified=True,
        )
        db_session.add(user)
        db_session.commit()

        wallet = CryptoWallet(user_id=600, coin_type="BTC", address="btc_addr_600", balance=1.0)
        db_session.add(wallet)
        db_session.commit()

        with patch(
            "backend.routes.crypto.crypto_service.initiate_withdrawal",
            new=AsyncMock(
                return_value={
                    "status": "pending",
                    "message": "Broadcasted",
                    "transaction_hash": "btc_tx_hash_001",
                }
            ),
        ):
            response = client.post(
                "/crypto/withdraw",
                json={"coin_type": "BTC", "amount": 0.1, "to_address": "bc1externaldest"},
            )

        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "awaiting_confirmation"
        assert data["transaction_hash"] == "btc_tx_hash_001"

        db_session.expire_all()
        updated_wallet = db_session.query(CryptoWallet).filter(CryptoWallet.user_id == 600, CryptoWallet.coin_type == "BTC").first()
        assert updated_wallet.balance == 0.89995
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_btc_deposit_waits_for_confirmations_then_credits(client, db_session):
    user = User(
        id=601,
        email="btc_dep_test@example.com",
        full_name="BTC Deposit Test",
        password_hash="hash",
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.commit()

    wallet = CryptoWallet(user_id=601, coin_type="BTC", address="btc_dep_addr_601", balance=0.0)
    db_session.add(wallet)
    db_session.commit()

    low_conf_payload = {
        "address": "btc_dep_addr_601",
        "coin_type": "BTC",
        "amount": 0.02,
        "transaction_hash": "btc_dep_hash_001",
        "confirmations": 1,
    }
    low_conf_resp = client.post("/crypto/webhook/deposit", json=low_conf_payload)
    assert low_conf_resp.status_code == 200
    assert "Awaiting confirmations" in low_conf_resp.json()["message"]

    db_session.expire_all()
    wallet_after_low_conf = db_session.query(CryptoWallet).filter(CryptoWallet.id == wallet.id).first()
    assert wallet_after_low_conf.balance == 0.0
    pending_tx = db_session.query(CryptoTransaction).filter(CryptoTransaction.transaction_hash == "btc_dep_hash_001").first()
    assert pending_tx is not None
    assert pending_tx.status == "pending"

    final_conf_payload = {
        "address": "btc_dep_addr_601",
        "coin_type": "BTC",
        "amount": 0.02,
        "transaction_hash": "btc_dep_hash_001",
        "confirmations": 3,
    }
    final_conf_resp = client.post("/crypto/webhook/deposit", json=final_conf_payload)
    assert final_conf_resp.status_code == 200
    assert "processed successfully" in final_conf_resp.json()["message"]

    db_session.expire_all()
    wallet_after_final = db_session.query(CryptoWallet).filter(CryptoWallet.id == wallet.id).first()
    assert wallet_after_final.balance == 0.02
    confirmed_tx = db_session.query(CryptoTransaction).filter(CryptoTransaction.transaction_hash == "btc_dep_hash_001").first()
    assert confirmed_tx.status == "confirmed"
