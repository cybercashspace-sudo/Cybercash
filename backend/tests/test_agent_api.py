from decimal import Decimal
import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.core.security import create_access_token
from backend.core.config import settings
from backend.models import Agent, AgentAPIKey, Transaction, User, Wallet
from backend.services.paystack_service import PaystackService


@pytest.fixture
def active_agent(db_session: Session):
    user = User(
        email="api-agent@example.com",
        password_hash="test-hash",
        is_active=True,
        is_verified=True,
        is_agent=True,
    )
    db_session.add(user)
    db_session.flush()
    wallet = Wallet(user_id=user.id, currency="GHS", balance=0)
    agent = Agent(user_id=user.id, status="active", float_balance=0)
    db_session.add_all([wallet, agent])
    db_session.commit()
    db_session.refresh(agent)
    headers = {"Authorization": f"Bearer {create_access_token(data={'sub': user.email})}"}
    return agent, wallet, headers


def _create_key(client: TestClient, agent_auth_headers: dict, mode: str = "live") -> str:
    response = client.post(
        "/agents/me/api-keys",
        json={"name": "Test storefront", "mode": mode},
        headers=agent_auth_headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["api_key"]


def test_agent_api_key_secret_is_returned_once_and_only_hash_is_stored(
    client: TestClient,
    db_session: Session,
    active_agent,
):
    agent, _wallet, headers = active_agent
    secret = _create_key(client, headers)
    assert secret.startswith("cc_agent_")

    stored = db_session.query(AgentAPIKey).filter_by(agent_id=agent.id).one()
    assert stored.key_hash != secret
    assert stored.key_hash

    listed = client.get("/agents/me/api-keys", headers=headers)
    assert listed.status_code == 200
    assert "api_key" not in listed.text
    assert secret not in listed.text
    assert listed.json()["items"][0]["prefix"] == secret[:24]
    assert listed.json()["items"][0]["mode"] == "live"
    assert listed.json()["items"][0]["public_key"].startswith("cc_pub_")


def test_inactive_agent_cannot_create_api_keys(client: TestClient, db_session: Session, active_agent):
    agent, _wallet, headers = active_agent
    agent.status = "pending"
    db_session.commit()
    response = client.post(
        "/agents/me/api-keys",
        json={"name": "Test storefront"},
        headers=headers,
    )
    assert response.status_code == 403


@pytest.mark.parametrize("account_change", [{"is_active": False}, {"is_verified": False}])
def test_disabled_or_unverified_owner_cannot_manage_api_keys(
    client: TestClient,
    db_session: Session,
    active_agent,
    account_change: dict,
):
    agent, _wallet, headers = active_agent
    owner = db_session.query(User).filter_by(id=agent.user_id).one()
    for field, value in account_change.items():
        setattr(owner, field, value)
    db_session.commit()

    response = client.post(
        "/agents/me/api-keys",
        json={"name": "Test storefront"},
        headers=headers,
    )

    assert response.status_code == 403
    assert "Verify and activate" in response.json()["detail"]


def test_agent_cannot_exceed_active_api_key_limit(client: TestClient, db_session: Session, active_agent):
    agent, _wallet, headers = active_agent
    for index in range(5):
        db_session.add(AgentAPIKey(
            agent_id=agent.id,
            name=f"Store {index}",
            mode="live",
            public_key=f"cc_pub_fixture_{index}",
            key_prefix=f"cc_agent_test{index}",
            key_hash=hashlib.sha256(f"secret-{index}".encode()).hexdigest(),
        ))
    db_session.commit()

    response = client.post(
        "/agents/me/api-keys",
        json={"name": "Another store"},
        headers=headers,
    )

    assert response.status_code == 409
    assert "up to 5 active API keys" in response.json()["detail"]
    assert db_session.query(AgentAPIKey).filter_by(agent_id=agent.id).count() == 5


def test_checkout_requires_key_and_idempotency_header(client: TestClient):
    response = client.post(
        "/agent-api/v1/payments/checkout",
        json={"amount": "20.00", "customer_email": "buyer@example.com"},
    )
    assert response.status_code == 422


def test_customer_checkout_is_idempotent_and_does_not_credit_before_confirmation(
    client: TestClient,
    db_session: Session,
    active_agent,
    monkeypatch: pytest.MonkeyPatch,
):
    _agent, active_agent_wallet, headers = active_agent
    secret = _create_key(client, headers)
    provider_calls = []

    async def fake_initiate(self, **kwargs):
        provider_calls.append(kwargs)
        return {
            "reference": "PS-AGENT-CHECKOUT-1",
            "authorization_url": "https://checkout.paystack.com/test-session",
            "access_code": "test-access-code",
        }

    monkeypatch.setattr(PaystackService, "initiate_payment", fake_initiate)
    headers = {
        "X-CyberCash-API-Key": secret,
        "Idempotency-Key": "customer-order-1001",
    }
    body = {"amount": "25.50", "customer_email": "buyer@example.com"}

    first = client.post("/agent-api/v1/payments/checkout", json=body, headers=headers)
    second = client.post("/agent-api/v1/payments/checkout", json=body, headers=headers)

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["reference"] == second.json()["reference"] == "PS-AGENT-CHECKOUT-1"
    assert len(provider_calls) == 1

    transaction = db_session.query(Transaction).filter_by(provider_reference="PS-AGENT-CHECKOUT-1").one()
    assert transaction.status == "pending"
    assert Decimal(str(transaction.amount)) == Decimal("25.50")
    assert "buyer@example.com" not in (transaction.metadata_json or "")
    assert Decimal(str(active_agent_wallet.balance)) == Decimal("0.00")

    monkeypatch.setattr(settings, "PAYSTACK_SECRET_KEY", "agent-api-webhook-test-secret")
    webhook = {
        "event": "charge.success",
        "data": {
            "reference": "PS-AGENT-CHECKOUT-1",
            "amount": 2550,
            "currency": "GHS",
            "status": "success",
            "customer": {"email": "buyer@example.com"},
        },
    }
    raw_body = json.dumps(webhook).encode("utf-8")
    signature = hmac.new(b"agent-api-webhook-test-secret", raw_body, hashlib.sha512).hexdigest()
    confirmed = client.post(
        "/paystack/webhook",
        content=raw_body,
        headers={"x-paystack-signature": signature},
    )

    assert confirmed.status_code == 200
    assert "wallet updated" in confirmed.json()["message"].lower()
    db_session.expire_all()
    assert Decimal(str(db_session.query(Wallet).filter_by(id=active_agent_wallet.id).one().balance)) == Decimal("25.50")
    status_response = client.get(
        "/agent-api/v1/payments/PS-AGENT-CHECKOUT-1",
        headers={"X-CyberCash-API-Key": secret},
    )
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "completed"


def test_test_api_key_never_calls_payment_provider_or_credits_wallet(
    client: TestClient,
    db_session: Session,
    active_agent,
    monkeypatch: pytest.MonkeyPatch,
):
    _agent, active_agent_wallet, headers = active_agent
    secret = _create_key(client, headers, mode="test")

    async def should_not_call_provider(self, **kwargs):
        pytest.fail("test mode must never call the live payment provider")

    monkeypatch.setattr(PaystackService, "initiate_payment", should_not_call_provider)
    request_headers = {
        "X-CyberCash-API-Key": secret,
        "Idempotency-Key": "sandbox-order-1001",
    }
    body = {"amount": "25.50", "customer_email": "buyer@example.com"}
    first = client.post("/agent-api/v1/payments/checkout", json=body, headers=request_headers)
    retry = client.post("/agent-api/v1/payments/checkout", json=body, headers=request_headers)

    assert first.status_code == retry.status_code == 201
    assert first.json() == retry.json()
    assert first.json()["status"] == "test"
    assert first.json()["reference"].startswith("CC-TEST-")
    assert first.json()["authorization_url"] is None
    transaction = db_session.query(Transaction).filter_by(provider_reference=first.json()["reference"]).one()
    assert transaction.provider == "cybercash_test"
    assert transaction.status == "test"
    assert Decimal(str(active_agent_wallet.balance)) == Decimal("0.00")

    status_response = client.get(
        f"/agent-api/v1/payments/{first.json()['reference']}",
        headers={"X-CyberCash-API-Key": secret},
    )
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "test"
    assert status_response.json()["environment"] == "test"


def test_revoked_agent_key_cannot_start_a_checkout(
    client: TestClient,
    db_session: Session,
    active_agent,
):
    _agent, _wallet, headers = active_agent
    secret = _create_key(client, headers)
    key = db_session.query(AgentAPIKey).one()
    response = client.delete(f"/agents/me/api-keys/{key.id}", headers=headers)
    assert response.status_code == 200

    denied = client.post(
        "/agent-api/v1/payments/checkout",
        json={"amount": "10.00", "customer_email": "buyer@example.com"},
        headers={"X-CyberCash-API-Key": secret, "Idempotency-Key": "customer-order-1002"},
    )
    assert denied.status_code == 401
