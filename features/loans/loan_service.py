from services.base_service import BaseApiService


class LoanService(BaseApiService):
    def check_eligibility(self):
        return self.get_json("/loans/eligibility")

    def apply(self, payload):
        return self.post_json("/loans/apply", payload)

    def repayments(self):
        return self.get_json("/loans/repayments")
