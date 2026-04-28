from api.client import API_URL, api_client

BASE_URL = API_URL


class APIService:
    def __init__(self):
        self.token = None

    def set_token(self, token):
        self.token = token

    def get_headers(self):
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def get_wallet(self):
        return api_client.get("/wallet", headers=self.get_headers())

    def send_money(self, data):
        return api_client.request(
            "POST",
            "/transfer",
            payload=data,
            headers=self.get_headers(),
        )
