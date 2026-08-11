from __future__ import annotations

from api.client import FAST_TIMEOUT, api_client
from core.exceptions import NetworkError


class WithdrawalService:
    def create_withdrawal(self, payload: dict) -> dict:
        result = api_client.request("POST", "/wallet/withdraw", payload=payload, timeout=FAST_TIMEOUT)
        status_code = int(result.get("status_code", 0) or 0)
        data = result.get("data", {})
        if status_code >= 400:
            message = ""
            if isinstance(data, dict):
                message = str(data.get("detail") or data.get("message") or "").strip()
            raise NetworkError(message or "Withdrawal request failed.")
        return data if isinstance(data, dict) else {"status": "pending", "payload": data}

    def check_status(self, withdrawal_id: str) -> dict:
        result = api_client.request("GET", f"/withdrawals/{withdrawal_id}", timeout=FAST_TIMEOUT)
        status_code = int(result.get("status_code", 0) or 0)
        data = result.get("data", {})
        if status_code >= 400:
            message = ""
            if isinstance(data, dict):
                message = str(data.get("detail") or data.get("message") or "").strip()
            raise NetworkError(message or "Unable to fetch withdrawal status.")
        return data if isinstance(data, dict) else {"status": "pending", "payload": data}
