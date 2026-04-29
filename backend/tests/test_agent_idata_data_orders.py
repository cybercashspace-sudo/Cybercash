from __future__ import annotations

import json

import pytest

from backend.core.security import create_access_token
from backend.models import Agent, BundleCatalog, DataOrder, Payment, Transaction, User, Wallet


@pytest.mark.asyncio
async def test_agent_can_purchase_idata_bundle(client, db_session, monkeypatch):
    # Arrange: agent user + wallet
    user = User(
        email="agent@example.com",
        password_hash="hashedpassword",
        is_active=True,
        is_agent=True,
        role="agent",
        status="active",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    wallet = Wallet(user_id=user.id, balance=50.0, currency="GHS")
    db_session.add(wallet)

    agent = Agent(user_id=user.id, status="active", commission_rate=0.02, float_balance=0.0, commission_balance=0.0)
    db_session.add(agent)

    bundle = BundleCatalog(
        network="MTN",
        bundle_code="IDATA_TEST",
        amount=5.0,
        currency="GHS",
        provider="idata",
        is_active=True,
        metadata_json=json.dumps({"idata_package_id": 5}),
    )
    db_session.add(bundle)
    db_session.commit()
    db_session.refresh(wallet)
    db_session.refresh(agent)
    db_session.refresh(bundle)

    # Patch iData provider call.
    from backend.routes import data_orders as data_orders_route

    data_orders_route.idata_service.api_key = "test_idata_key"
    data_orders_route.idata_service.base_url = "https://idatagh.test/wp-json/custom/v1"

    async def _fake_place_order(*, network: str, beneficiary: str, bundle_package_id: int) -> dict:
        assert network == "mtn"
        assert beneficiary == "0241234567"
        assert bundle_package_id == 5
        return {"status": "success", "order_id": "IDATA_ORDER_123"}

    monkeypatch.setattr(data_orders_route.idata_service, "place_order", _fake_place_order, raising=True)

    token = create_access_token(data={"sub": user.email})
    headers = {"Authorization": f"Bearer {token}"}

    # Act
    response = client.post(
        "/agent/data",
        json={"network": "mtn", "phone": "0241234567", "bundle_id": bundle.id},
        headers=headers,
    )

    # Assert
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["order"]["status"] == "completed"
    assert payload["order"]["status_label"] == "Complete"
    assert payload["order"]["provider"] == "idata"
    assert payload["provider_response"]["order_id"] == "IDATA_ORDER_123"
    assert float(payload["order"]["amount"]) == 4.5

    db_session.refresh(wallet)
    assert wallet.balance == 45.5

    # Order + transaction persisted.
    order_row = db_session.query(DataOrder).filter(DataOrder.id == payload["order"]["id"]).first()
    assert order_row is not None
    assert order_row.bundle_catalog_id == bundle.id
    assert order_row.bundle_id == 5

    tx_row = db_session.query(Transaction).filter(Transaction.id == payload["transaction_id"]).first()
    assert tx_row is not None
    assert tx_row.provider == "idata"

    payment_row = db_session.query(Payment).filter(Payment.id == payload["payment_id"]).first()
    assert payment_row is not None
    assert payment_row.processor == "idata"


@pytest.mark.asyncio
async def test_agent_idata_order_status_label_shows_ordered_when_provider_reports_ordered(client, db_session, monkeypatch):
    user = User(
        email="agent-ordered@example.com",
        password_hash="hashedpassword",
        is_active=True,
        is_agent=True,
        role="agent",
        status="active",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    wallet = Wallet(user_id=user.id, balance=50.0, currency="GHS")
    db_session.add(wallet)

    agent = Agent(user_id=user.id, status="active", commission_rate=0.02, float_balance=0.0, commission_balance=0.0)
    db_session.add(agent)

    bundle = BundleCatalog(
        network="MTN",
        bundle_code="IDATA_ORDERED",
        amount=5.0,
        currency="GHS",
        provider="idata",
        is_active=True,
        metadata_json=json.dumps({"idata_package_id": 5}),
    )
    db_session.add(bundle)
    db_session.commit()
    db_session.refresh(wallet)
    db_session.refresh(agent)
    db_session.refresh(bundle)

    from backend.routes import data_orders as data_orders_route

    data_orders_route.idata_service.api_key = "test_idata_key"
    data_orders_route.idata_service.base_url = "https://idatagh.test/wp-json/custom/v1"

    async def _fake_place_order(*, network: str, beneficiary: str, bundle_package_id: int) -> dict:
        assert network == "mtn"
        assert beneficiary == "0241234567"
        assert bundle_package_id == 5
        return {"status": "ordered", "order_id": "IDATA_ORDER_456"}

    monkeypatch.setattr(data_orders_route.idata_service, "place_order", _fake_place_order, raising=True)

    token = create_access_token(data={"sub": user.email})
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        "/agent/data",
        json={"network": "mtn", "phone": "0241234567", "bundle_id": bundle.id},
        headers=headers,
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["order"]["status"] == "pending"
    assert payload["order"]["status_label"] == "Ordered"
    assert payload["provider_response"]["status"] == "ordered"


def test_non_agent_cannot_purchase_idata_bundle(client, db_session):
    user = User(
        email="user@example.com",
        password_hash="hashedpassword",
        is_active=True,
        is_agent=False,
        role="user",
        status="active",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    token = create_access_token(data={"sub": user.email})
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        "/agent/data",
        json={"network": "mtn", "phone": "0241234567", "bundle_id": 1},
        headers=headers,
    )
    assert response.status_code == 403
