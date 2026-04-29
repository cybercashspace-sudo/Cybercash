from __future__ import annotations

import json

from backend.core.security import create_access_token
from backend.models import BundleCatalog, Transaction, User, Wallet


def test_user_can_purchase_idata_bundle_via_bundles_route(client, db_session, monkeypatch):
    user = User(
        email="idata_user@example.com",
        password_hash="hashedpassword",
        is_active=True,
        is_verified=True,
        role="user",
        status="active",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    wallet = Wallet(user_id=user.id, balance=20.0, currency="GHS")
    db_session.add(wallet)

    bundle = BundleCatalog(
        network="MTN",
        bundle_code="1GB",
        amount=5.0,
        currency="GHS",
        provider="idata",
        is_active=True,
        metadata_json=json.dumps({"idata_package_id": 5}),
    )
    db_session.add(bundle)
    db_session.commit()
    db_session.refresh(wallet)
    db_session.refresh(bundle)

    from backend.routes import bundles as bundles_route

    bundles_route.idata_service.api_key = "test_idata_key"
    bundles_route.idata_service.base_url = "https://idatagh.test/wp-json/custom/v1"

    async def _fake_place_order(*, network: str, beneficiary: str, bundle_package_id: int) -> dict:
        assert network == "mtn"
        assert beneficiary == "0241234567"
        assert bundle_package_id == 5
        return {"status": "success", "order_id": "IDATA_ORDER_ABC"}

    monkeypatch.setattr(bundles_route.idata_service, "place_order", _fake_place_order, raising=True)

    token = create_access_token(data={"sub": user.email})
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        "/api/bundles/purchase",
        json={"network": "MTN", "bundle_code": "1GB", "phone": "0241234567"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["type"].lower() == "data"
    assert float(payload["amount"]) == 5.0

    db_session.refresh(wallet)
    assert wallet.balance == 15.0

    tx_row = db_session.query(Transaction).filter(Transaction.id == payload["id"]).first()
    assert tx_row is not None
    assert tx_row.status == "completed"
    assert tx_row.provider == "idata"
    assert tx_row.provider_reference

