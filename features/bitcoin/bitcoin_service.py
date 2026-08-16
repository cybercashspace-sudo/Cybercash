from services.base_service import BaseApiService


class BitcoinService(BaseApiService):
    def get_wallet(self):
        return self.get_json("/btc/wallet")

    def get_transactions(self, page=1, limit=20):
        payload = self.get_json("/btc/transactions", params={"page": page, "limit": limit})
        return self.extract_items(payload)

    def create_deposit_address(self):
        return self.post_json("/btc/deposit-address", {})

    def buy(self, payload):
        return self.post_json("/btc/buy", payload)

    def sell(self, payload):
        return self.post_json("/btc/sell", payload)

    def withdraw(self, payload):
        return self.post_json("/btc/withdraw", payload)
