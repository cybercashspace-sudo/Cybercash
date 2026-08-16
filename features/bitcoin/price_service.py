from services.base_service import BaseApiService


class PriceService(BaseApiService):
    def get_btc_price(self):
        payload = self.get_json("/btc/price")

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
