from services.api import api


class AgentService:
    def profile(self):
        response = api.get("/agent/profile")
        response.raise_for_status()
        return response.json()

    def apply(self, payload):
        response = api.post("/agent/apply", payload)
        response.raise_for_status()
        return response.json()

    def kyc(self, payload):
        response = api.post("/agent/kyc", payload)
        response.raise_for_status()
        return response.json()

    def commissions(self):
        response = api.get("/agent/commissions")
        response.raise_for_status()
        return response.json()

    def transactions(self):
        response = api.get("/agent/transactions")
        response.raise_for_status()
        return response.json()

