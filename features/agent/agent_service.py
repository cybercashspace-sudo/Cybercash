from services.base_service import BaseApiService


class AgentService(BaseApiService):
    def profile(self):
        return self.get_json("/agent/profile")

    def apply(self, payload):
        return self.post_json("/agent/apply", payload)

    def commissions(self):
        return self.get_json("/agent/commissions")

    def transactions(self):
        return self.get_json("/agent/transactions")

    def api_keys(self):
        return self.get_json("/agents/me/api-keys")

    def create_api_key(self, name: str, mode: str = "live"):
        # This operation returns the secret only once. Keep it on the active
        # backend and do not transparently replay it on a timeout/failover.
        return self.post_json("/agents/me/api-keys", {"name": name, "mode": mode}, failover=False)

    def revoke_api_key(self, key_id: int):
        return self.request_json("DELETE", f"/agents/me/api-keys/{int(key_id)}")
