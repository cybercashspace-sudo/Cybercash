from services.base_service import BaseApiService


class DataService(BaseApiService):
    def packages(self, network):
        return self.get_json(f"/data/packages/{network}")

    def purchase(self, payload):
        return self.post_json("/data/buy", payload)

    def history(self, page=1, limit=20):
        return self.get_json("/data/history", params={"page": page, "limit": limit})
