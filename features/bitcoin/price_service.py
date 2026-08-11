from services.api import api


class PriceService:
    def get_btc_price(self):
        response = api.get("/btc/price")
        response.raise_for_status()
        payload = response.json()

        if isinstance(payload, dict):
            for key in ("price", "btc_price", "usd_price", "rate"):
                value = payload.get(key)
                if value is not None:
                    try:
                        return float(value)
                    except (TypeError, ValueError):
                        continue
        try:
            return float(payload)
        except (TypeError, ValueError):
            return 0.0

