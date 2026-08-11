from services.api import api


class AirtimeService:
    def purchase(self, payload):
        response = api.post("/airtime/buy", payload)
        response.raise_for_status()
        return response.json()

    def history(self, page=1, limit=20):
        response = api.get(f"/airtime/history?page={page}&limit={limit}")
        response.raise_for_status()
        return response.json()

