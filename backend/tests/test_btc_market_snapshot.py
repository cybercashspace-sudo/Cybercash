from backend.routes import crypto


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_btc_market_uses_live_btc_and_usd_ghs_quotes(monkeypatch):
    crypto._fx_cache.update(rate=None, updated_at=0.0, source_updated_at=None)
    responses = iter([
        _Response({
            "lastPrice": "65000",
            "priceChangePercent": "2.5",
            "highPrice": "66000",
            "lowPrice": "63000",
            "volume": "1000",
        }),
        _Response({
            "data": {
                "latest_value": 11.5,
                "latest_at": "2026-11-27T00:00:00+00:00",
                "stale": False,
            }
        }),
    ])
    monkeypatch.setattr(crypto.requests, "get", lambda *_args, **_kwargs: next(responses))

    snapshot = crypto.get_btc_market_snapshot()

    assert snapshot["last_price_usdt"] == 65000
    assert snapshot["usd_to_ghs_rate"] == 11.5
    assert snapshot["estimated_ghs_per_btc"] == 747500
    assert snapshot["fx_source"] == "API Ghana"
    assert snapshot["fx_updated_at"] == "2026-11-27T00:00:00+00:00"


def test_btc_market_keeps_usd_quote_when_fx_is_unavailable(monkeypatch):
    crypto._fx_cache.update(rate=None, updated_at=0.0, source_updated_at=None)
    responses = iter([
        _Response({
            "lastPrice": "65000",
            "priceChangePercent": "2.5",
            "highPrice": "66000",
            "lowPrice": "63000",
            "volume": "1000",
        }),
        RuntimeError("provider details must not be shown"),
    ])

    def fake_get(*_args, **_kwargs):
        item = next(responses)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(crypto.requests, "get", fake_get)

    snapshot = crypto.get_btc_market_snapshot()

    assert snapshot["last_price_usdt"] == 65000
    assert snapshot["usd_to_ghs_rate"] is None
    assert snapshot["estimated_ghs_per_btc"] is None
    assert snapshot["fx_source"] is None
