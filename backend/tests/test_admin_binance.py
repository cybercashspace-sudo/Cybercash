from __future__ import annotations

import pytest

from backend.core.security import create_access_token
from backend.models import User


def test_binance_admin_requires_admin(client, db_session):
    user = User(
        email="basic@example.com",
        password_hash="hashedpassword",
        is_admin=False,
        is_active=True,
        role="user",
        status="active",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    token = create_access_token(data={"sub": user.email})
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get("/admin/binance/health", headers=headers)
    assert resp.status_code == 403


def test_binance_admin_health_ok(client, admin_auth_headers):
    resp = client.get("/admin/binance/health", headers=admin_auth_headers)
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert "configured" in payload
    assert payload["base_url"]


def test_binance_admin_balance_uses_service(client, admin_auth_headers, monkeypatch):
    from backend.routes import binance_admin as binance_admin_route

    monkeypatch.setattr(binance_admin_route.binance_service, "is_configured", lambda: True, raising=True)

    async def _fake_balance(asset: str) -> dict:
        assert asset == "BTC"
        return {"asset": "BTC", "free": "1.25", "locked": "0.0"}

    monkeypatch.setattr(binance_admin_route.binance_service, "get_asset_balance", _fake_balance, raising=True)

    resp = client.get("/admin/binance/balance/BTC", headers=admin_auth_headers)
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["asset"] == "BTC"
    assert payload["free"] == 1.25


def test_binance_withdraw_disabled_by_default(client, admin_auth_headers):
    resp = client.post(
        "/admin/binance/withdraw",
        headers=admin_auth_headers,
        json={"coin": "BTC", "address": "bc1qexample", "amount": 0.01},
    )
    assert resp.status_code == 403


def test_binance_admin_btc_dashboard_combines_fields(client, admin_auth_headers, monkeypatch):
    from backend.routes import binance_admin as binance_admin_route

    monkeypatch.setattr(binance_admin_route.binance_service, "is_configured", lambda: True, raising=True)

    async def _fake_price(symbol: str) -> float:
        assert symbol == "BTCUSDT"
        return 100000.0

    async def _fake_balance(asset: str) -> dict:
        assert asset == "BTC"
        return {"asset": "BTC", "free": "0.5", "locked": "0.1"}

    async def _fake_address(*, coin: str, network=None) -> dict:
        assert coin == "BTC"
        return {"address": "bc1qexampleaddress", "network": "BTC", "tag": None}

    monkeypatch.setattr(binance_admin_route.binance_service, "get_symbol_price", _fake_price, raising=True)
    monkeypatch.setattr(binance_admin_route.binance_service, "get_asset_balance", _fake_balance, raising=True)
    monkeypatch.setattr(binance_admin_route.binance_service, "get_deposit_address", _fake_address, raising=True)

    resp = client.get("/admin/binance/btc/dashboard", headers=admin_auth_headers)
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["configured"] is True
    assert payload["btc_balance"] == 0.5
    assert payload["usd_price"] == 100000.0
    assert payload["address"] == "bc1qexampleaddress"
