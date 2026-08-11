from services.api import api


class BitcoinService:
    @staticmethod
    def _items(payload):
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            for key in ("items", "results", "transactions", "data"):
                value = payload.get(key)
                if isinstance(value, list):
                    return value
        return []

    def get_wallet(self):
        response = api.get("/btc/wallet")
        response.raise_for_status()
        return response.json()

    def get_transactions(self, page=1, limit=20):
        response = api.get(f"/btc/transactions?page={page}&limit={limit}")
        response.raise_for_status()
        payload = response.json()
        return self._items(payload)

    def create_deposit_address(self):
        response = api.post("/btc/deposit-address", {})
        response.raise_for_status()
        return response.json()

    def buy(self, payload):
        response = api.post("/btc/buy", payload)
        response.raise_for_status()
        return response.json()

    def sell(self, payload):
        response = api.post("/btc/sell", payload)
        response.raise_for_status()
        return response.json()

    def withdraw(self, payload):
        response = api.post("/btc/withdraw", payload)
        response.raise_for_status()
        return response.json()

