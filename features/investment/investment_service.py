from services.base_service import BaseApiService


class InvestmentService(BaseApiService):
    def plans(self):
        return self.get_json("/investment/plans")

    def create(self, payload):
        return self.post_json("/investment/create", payload)

    def history(self):
        return self.get_json("/investment/history")
