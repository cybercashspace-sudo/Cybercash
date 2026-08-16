from services.api import API_URL
from services.base_service import BaseApiService

BASE_URL = API_URL


class APIService(BaseApiService):
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
        return self.get_json("/wallet", headers=self.get_headers())

    def send_money(self, data):
        return self.post_json("/transfer", data, headers=self.get_headers())
