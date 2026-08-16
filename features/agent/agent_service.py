from services.base_service import BaseApiService


class AgentService(BaseApiService):
    def profile(self):
        return self.get_json("/agent/profile")

    def apply(self, payload):
        return self.post_json("/agent/apply", payload)

    def kyc(self, payload):
        return self.post_json("/agent/kyc", payload)

    def commissions(self):
        return self.get_json("/agent/commissions")

    def transactions(self):
        return self.get_json("/agent/transactions")
