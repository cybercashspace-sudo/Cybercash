from __future__ import annotations

from datetime import datetime, timezone

import requests

from core.message_sanitizer import sanitize_backend_message
from services.api import FAST_TIMEOUT
from services.base_service import BaseApiService


class MarketService(BaseApiService):
    def get_btc_snapshot(self) -> dict:
        try:
            payload = self.get_json("/crypto/market/btc", timeout=FAST_TIMEOUT)
            if isinstance(payload, dict) and payload.get("last_price_usdt") is not None:
                return payload
        except Exception:
            pass

        try:
            response = requests.get("https://api.binance.com/api/v3/ticker/24hr?symbol=BTCUSDT", timeout=8)
            response.raise_for_status()
            market = response.json()
            last_price = float(market.get("lastPrice") or market.get("price") or 0.0)
            return {
                "symbol": "BTCUSDT",
                "network": "Bitcoin",
                "min_deposit_btc": 0.0001,
                "withdrawal_fee_btc": 0.00005,
                "last_price_usdt": last_price,
                "price_change_percent_24h": float(market.get("priceChangePercent") or 0.0),
                "high_price_usdt": float(market.get("highPrice") or 0.0),
                "low_price_usdt": float(market.get("lowPrice") or 0.0),
                "volume_btc": float(market.get("volume") or 0.0),
                "usd_to_ghs_rate": 12.0,
                "estimated_ghs_per_btc": last_price * 12.0,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "source": "binance",
            }
        except Exception as exc:
            return {"error": sanitize_backend_message(exc, fallback="Unable to load BTC market data.")}
