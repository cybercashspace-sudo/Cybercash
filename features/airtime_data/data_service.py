from services.api import api


class DataService:
    def packages(self, network):
        response = api.get(f"/data/packages/{network}")
        response.raise_for_status()
        return response.json()

    def purchase(self, payload):
        response = api.post("/data/buy", payload)
        response.raise_for_status()
        return response.json()

    def history(self, page=1, limit=20):
        response = api.get(f"/data/history?page={page}&limit={limit}")
        response.raise_for_status()
        return response.json()

