from services.api import api


class LoanService:
    def check_eligibility(self):
        response = api.get("/loans/eligibility")
        response.raise_for_status()
        return response.json()

    def apply(self, payload):
        response = api.post("/loans/apply", payload)
        response.raise_for_status()
        return response.json()

    def repayments(self):
        response = api.get("/loans/repayments")
        response.raise_for_status()
        return response.json()

