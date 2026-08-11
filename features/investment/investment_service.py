from services.api import api


class InvestmentService:
    def plans(self):
        response = api.get("/investment/plans")
        response.raise_for_status()
        return response.json()

    def create(self, payload):
        response = api.post("/investment/create", payload)
        response.raise_for_status()
        return response.json()

    def history(self):
        response = api.get("/investment/history")
        response.raise_for_status()
        return response.json()

