from services.base_service import BaseApiService


class AirtimeService(BaseApiService):
    def purchase(self, payload):
        return self.post_json("/airtime/buy", payload)

    def history(self, page=1, limit=20):
        return self.get_json("/airtime/history", params={"page": page, "limit": limit})
