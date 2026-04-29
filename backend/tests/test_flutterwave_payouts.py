from __future__ import annotations

import json

import pytest

from backend.core.security import create_access_token
from backend.models import Agent, Payment, Transaction, User, Wallet
from backend.services import flutterwave_service as flutterwave_module
from backend.services.flutterwave_service import FlutterwaveService


def _auth_headers(user_id: int) -> dict:
    token = create_access_token(data={"sub": str(user_id)})
    return {"Authorization": f"Bearer {token}"}


def _create_user(
    db_session,
    *,
    user_id: int,
    email: str,
    role: str,
    is_admin: bool = False,
    is_agent: bool = False,
    is_verified: bool = True,
    wallet_balance: float = 0.0,
) -> User:
    user = User(
        id=user_id,
        email=email,
        full_name=email.split("@")[0],
        password_hash="hash",
        is_active=True,
        is_verified=is_verified,
        is_admin=is_admin,
        is_agent=is_agent,
        role=role,
        status="active",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    wallet = Wallet(user_id=user.id, currency="GHS", balance=wallet_balance)
    db_session.add(wallet)
    db_session.commit()
    return user


def test_withdraw_rejects_non_admin_or_agent(client, db_session):
    user = _create_user(
        db_session,
        user_id=901,
        email="payout_user@test.com",
        role="user",
        wallet_balance=100.0,
    )

    response = client.post(
        "/withdraw",
        json={
            "user_id": user.id,
            "amount": 25.0,
            "method": "momo",
            "account_number": "0241234567",
        },
        headers=_auth_headers(user.id),
    )

    assert response.status_code == 403
    assert "withdrawal not allowed" in response.json()["detail"].lower()


def test_withdraw_auto_detects_network_and_reserves_wallet_balance(client, db_session):
    admin = _create_user(
        db_session,
        user_id=902,
        email="admin_payout@test.com",
        role="admin",
        is_admin=True,
        wallet_balance=500.0,
    )

    response = client.post(
        "/withdraw",
        json={
            "user_id": admin.id,
            "amount": 125.5,
            "method": "momo",
            "account_number": "0201234567",
            "notes": "Admin payout",
        },
        headers=_auth_headers(admin.id),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["processor"] == "flutterwave"
    assert payload["status"] == "awaiting_confirmation"

    db_session.expire_all()
    payment = db_session.query(Payment).filter(Payment.user_id == admin.id).order_by(Payment.id.desc()).first()
    wallet = db_session.query(Wallet).filter(Wallet.user_id == admin.id).first()
    assert payment is not None
    assert wallet is not None
    assert round(float(wallet.balance), 2) == 374.5

    metadata = json.loads(payment.metadata_json or "{}")
    assert metadata["method"] == "momo"
    assert metadata["detected_network"] == "VODAFONE"
    assert metadata["momo_number_flutterwave"] == "233201234567"


def test_agent_withdraw_uses_commission_balance(client, db_session):
    agent_user = _create_user(
        db_session,
        user_id=903,
        email="agent_payout@test.com",
        role="agent",
        is_agent=True,
        wallet_balance=0.0,
    )
    agent = Agent(
        user_id=agent_user.id,
        status="active",
        business_name="Agent Payout Shop",
        commission_rate=0.02,
        float_balance=10.0,
        commission_balance=80.0,
    )
    db_session.add(agent)
    db_session.commit()

    response = client.post(
        "/withdraw",
        json={
            "user_id": agent_user.id,
            "amount": 30.0,
            "method": "momo",
            "account_number": "0243334444",
        },
        headers=_auth_headers(agent_user.id),
    )

    assert response.status_code == 200
    db_session.expire_all()

    agent_row = db_session.query(Agent).filter(Agent.user_id == agent_user.id).first()
    wallet = db_session.query(Wallet).filter(Wallet.user_id == agent_user.id).first()
    payment = db_session.query(Payment).filter(Payment.user_id == agent_user.id).order_by(Payment.id.desc()).first()

    assert agent_row is not None
    assert wallet is not None
    assert round(float(agent_row.commission_balance), 2) == 50.0
    assert round(float(wallet.balance), 2) == 0.0
    assert payment is not None

    metadata = json.loads(payment.metadata_json or "{}")
    assert metadata["source_kind"] == "agent_commission"
    assert metadata["detected_network"] == "MTN"


def test_flutterwave_webhook_success_marks_payout_completed(client, db_session):
    user = _create_user(
        db_session,
        user_id=904,
        email="webhook_payout@test.com",
        role="admin",
        is_admin=True,
        wallet_balance=200.0,
    )

    payment = Payment(
        user_id=user.id,
        amount=40.0,
        currency="GHS",
        processor="flutterwave",
        type="withdrawal",
        status="awaiting_confirmation",
        our_transaction_id="CYBERCASH-PAYOUT-904-REFERENCE",
    )
    db_session.add(payment)
    db_session.commit()
    db_session.refresh(payment)

    wallet = db_session.query(Wallet).filter(Wallet.user_id == user.id).first()
    transaction = Transaction(
        user_id=user.id,
        wallet_id=wallet.id,
        amount=40.0,
        currency="GHS",
        type="MOBILE_MONEY",
        status="awaiting_confirmation",
        provider="flutterwave",
        provider_reference=payment.our_transaction_id,
        metadata_json=json.dumps(
            {
                "payment_id": payment.id,
                "source_kind": "wallet",
                "source_ledger_account": "Customer Wallets (Liability)",
            }
        ),
    )
    db_session.add(transaction)
    db_session.commit()

    response = client.post(
        "/webhooks/flutterwave",
        headers={"verif-hash": "test_flutterwave_webhook_hash"},
        json={
            "event": "transfer.completed",
            "data": {
                "id": "FLW_TEST_ID",
                "reference": payment.our_transaction_id,
                "status": "SUCCESSFUL",
            },
        },
    )

    assert response.status_code == 200
    db_session.expire_all()

    payment = db_session.query(Payment).filter(Payment.id == payment.id).first()
    transaction = db_session.query(Transaction).filter(Transaction.id == transaction.id).first()
    wallet = db_session.query(Wallet).filter(Wallet.user_id == user.id).first()

    assert payment is not None
    assert transaction is not None
    assert wallet is not None
    assert payment.status == "successful"
    assert transaction.status == "completed"
    assert round(float(wallet.balance), 2) == 200.0


def test_flutterwave_webhook_rejects_invalid_signature(client):
    response = client.post(
        "/webhooks/flutterwave",
        headers={"verif-hash": "wrong-hash"},
        json={
            "event": "transfer.completed",
            "data": {
                "id": "FLW_TEST_ID",
                "reference": "CYBERCASH-PAYOUT-INVALID",
                "status": "SUCCESSFUL",
            },
        },
    )

    assert response.status_code == 400
    assert "invalid webhook signature" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_flutterwave_service_uses_oauth_token_for_transfers(monkeypatch):
    captured: dict = {}
    monkeypatch.setenv("FLW_CLIENT_ID", "test_flw_client_id")
    monkeypatch.setenv("FLW_CLIENT_SECRET", "test_flw_client_secret")
    monkeypatch.setenv("FLW_ENCRYPTION_KEY", "MDEyMzQ1Njc4OWFiY2RlZg==")

    class FakeResponse:
        def __init__(self, payload, status_code=200):
            self._payload = payload
            self.status_code = status_code
            self.text = json.dumps(payload)

        def json(self):
            return self._payload

        def raise_for_status(self):
            return None

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            captured["client_timeout"] = kwargs.get("timeout")

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, headers=None, data=None, json=None):
            if url.endswith("/oauth/token"):
                captured["token_url"] = url
                captured["token_headers"] = headers or {}
                captured["token_data"] = data or {}
                return FakeResponse(
                    {
                        "access_token": "oauth-access-token",
                        "expires_in": 3600,
                    }
                )

            captured["transfer_url"] = url
            captured["transfer_headers"] = headers or {}
            captured["transfer_json"] = json or {}
            return FakeResponse(
                {
                    "status": "success",
                    "message": "accepted",
                    "data": {
                        "id": "FLW_TEST_TRANSFER",
                        "status": "NEW",
                        "reference": (json or {}).get("reference"),
                    },
                }
            )

        async def get(self, url, headers=None):
            captured["get_url"] = url
            captured["get_headers"] = headers or {}
            return FakeResponse(
                {
                    "status": "success",
                    "data": {
                        "id": "FLW_TEST_TRANSFER",
                        "status": "SUCCESSFUL",
                    },
                }
            )

    monkeypatch.setattr(flutterwave_module.httpx, "AsyncClient", FakeAsyncClient, raising=True)

    service = FlutterwaveService()
    token = await service._get_oauth_token()
    auth_headers = await service._get_auth_headers()

    assert captured["token_url"].endswith("/oauth/token")
    assert captured["token_headers"]["Authorization"].startswith("Basic ")
    assert captured["token_data"]["grant_type"] == "client_credentials"
    assert token == "oauth-access-token"
    assert auth_headers["Authorization"] == "Bearer oauth-access-token"
