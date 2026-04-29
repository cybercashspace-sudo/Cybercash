from unittest.mock import AsyncMock, patch

from backend.main import app
from backend.dependencies.auth import get_current_user
from backend.models import Payment, Transaction, User, Wallet


def override_get_current_user_momo():
    return User(
        id=300,
        email="momo_funding_test@example.com",
        full_name="Momo Funding Test",
        is_active=True,
        is_verified=True,
    )


def test_momo_funding_initiate_creates_pending_payment_and_transaction(client, db_session):
    app.dependency_overrides[get_current_user] = override_get_current_user_momo
    try:
        user = User(
            id=300,
            email="momo_funding_test@example.com",
            full_name="Momo Funding Test",
            password_hash="hash",
            is_active=True,
            is_verified=True,
        )
        db_session.add(user)
        db_session.commit()

        with patch(
            "backend.routes.payments.momo_service.initiate_deposit",
            new=AsyncMock(
                return_value={
                    "status": "pending",
                    "message": "Awaiting confirmation",
                    "processor_transaction_id": "MOMO_DEP_REF_1",
                }
            ),
        ):
            response = client.post(
                "/payments/momo/deposit/initiate",
                json={"amount": 100.0, "currency": "GHS", "phone_number": "0240000000"},
            )

        assert response.status_code == 202
        payment = db_session.query(Payment).filter(Payment.user_id == 300).first()
        tx = db_session.query(Transaction).filter(Transaction.user_id == 300).first()
        wallet = db_session.query(Wallet).filter(Wallet.user_id == 300).first()

        assert payment is not None
        assert payment.status == "awaiting_confirmation"
        assert tx is not None
        assert tx.status == "pending"
        assert tx.type == "FUNDING"
        assert wallet is not None
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_momo_funding_callback_success_credits_wallet(client, db_session):
    app.dependency_overrides[get_current_user] = override_get_current_user_momo
    try:
        user = User(
            id=300,
            email="momo_funding_test@example.com",
            full_name="Momo Funding Test",
            password_hash="hash",
            is_active=True,
            is_verified=True,
        )
        db_session.add(user)
        db_session.commit()

        wallet = Wallet(user_id=300, currency="GHS", balance=0.0)
        db_session.add(wallet)
        db_session.commit()
        db_session.refresh(wallet)

        payment = Payment(
            user_id=300,
            processor="momo",
            type="deposit",
            amount=75.0,
            currency="GHS",
            status="awaiting_confirmation",
            our_transaction_id="DEP_TEST_REF",
        )
        db_session.add(payment)
        db_session.commit()
        db_session.refresh(payment)

        tx = Transaction(
            user_id=300,
            wallet_id=wallet.id,
            type="FUNDING",
            amount=75.0,
            currency="GHS",
            status="pending",
            provider="momo",
            provider_reference="DEP_TEST_REF",
            metadata_json=f'{{"payment_id": {payment.id}}}',
        )
        db_session.add(tx)
        db_session.commit()

        response = client.post(
            f"/payments/momo/callback/{payment.id}",
            json={"status": "successful", "processor_transaction_id": "MOMO_DEP_FINAL_1"},
        )
        assert response.status_code == 200

        db_session.expire_all()
        wallet = db_session.query(Wallet).filter(Wallet.user_id == 300).first()
        payment = db_session.query(Payment).filter(Payment.id == payment.id).first()
        tx = db_session.query(Transaction).filter(Transaction.id == tx.id).first()

        assert wallet.balance == 75.0
        assert payment.status == "successful"
        assert tx.status == "completed"
    finally:
        app.dependency_overrides.pop(get_current_user, None)
