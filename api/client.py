import threading

import requests
from requests.adapters import HTTPAdapter

from core.config import config as app_config
from core.environment import load_runtime_environment, resolve_api_base_url, resolve_api_urls
from core.session import session
from core.message_sanitizer import sanitize_backend_message

load_runtime_environment()

try:
    from urllib3.util.retry import Retry
except Exception:
    Retry = None

DEFAULT_CONNECT_TIMEOUT_SECONDS = 4
DEFAULT_READ_TIMEOUT_SECONDS = int(getattr(app_config, "request_timeout", 15) or 15)
DEFAULT_TIMEOUT = (DEFAULT_CONNECT_TIMEOUT_SECONDS, DEFAULT_READ_TIMEOUT_SECONDS)
FAST_TIMEOUT = (2, 6)
RETRY_STATUS_CODES = (429, 500, 502, 503, 504)
FAILOVER_STATUS_CODES = (502, 503, 504)
PAYSTACK_FAILOVER_STATUS_CODES = (500, 502, 503, 504)
AUTH_FAILOVER_STATUS_CODES = (401, 403)


def _is_payment_reference_path(path: str) -> bool:
    lower_path = str(path or "").lower()
    if lower_path.startswith("/paystack/") or "/paystack/" in lower_path:
        return True
    if lower_path.startswith("/api/paystack/") or "/api/paystack/" in lower_path:
        return True
    if lower_path.startswith("/api/wallet/topup/paystack/"):
        return True
    return lower_path == "/agents/register" or lower_path.startswith("/agents/register/")


def _coerce_timeout(timeout):
    if timeout is None:
        return DEFAULT_TIMEOUT
    if isinstance(timeout, (tuple, list)) and len(timeout) == 2:
        return float(timeout[0]), float(timeout[1])
    return DEFAULT_CONNECT_TIMEOUT_SECONDS, float(timeout)


API_URL = resolve_api_base_url()


class APIClient:
    def __init__(self, base_url: str | None = None):
        self.base_url = str(base_url or API_URL).rstrip("/")
        self.base_urls = [self.base_url]
        if base_url is None:
            self.base_urls = resolve_api_urls()
            self.base_url = self.base_urls[0]
        self.session = requests.Session()
        self._request_lock = threading.RLock()
        self._install_retries()

    def _install_retries(self) -> None:
        if Retry is None:
            return

        retry = Retry(
            total=1,
            connect=1,
            read=0,
            status=1,
            backoff_factor=0.25,
            status_forcelist=RETRY_STATUS_CODES,
            allowed_methods=frozenset({"GET", "POST", "PUT", "PATCH"}),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    @staticmethod
    def _safe_json(response):
        try:
            return response.json() if response.content else {}
        except Exception:
            text = (response.text or "").strip()
            return {"detail": sanitize_backend_message(text or f"HTTP {response.status_code}")}

    @staticmethod
    def _timeout_message(exc: Exception) -> str:
        message = sanitize_backend_message(exc)
        if isinstance(exc, requests.exceptions.Timeout) or "timed out" in message.lower():
            return "Backend connection timed out. Please check your internet connection and try again."
        return message

    def _ordered_base_urls(self) -> list[str]:
        urls = []
        active = str(self.base_url or "").rstrip("/")
        if active:
            urls.append(active)
        for base_url in self.base_urls:
            normalized = str(base_url or "").rstrip("/")
            if normalized and normalized not in urls:
                urls.append(normalized)
        return urls

    @staticmethod
    def _has_auth_header(headers: dict | None) -> bool:
        if not headers:
            return False
        return bool(str(headers.get("Authorization", "") or "").strip())

    def request(
        self,
        method: str,
        path: str,
        payload: dict | None = None,
        params: dict | None = None,
        headers: dict | None = None,
        timeout=DEFAULT_TIMEOUT,
        failover: bool = True,
    ) -> dict:
        last_result = None
        request_headers = dict(headers or {})
        request_headers.setdefault("Content-Type", "application/json")
        if session.authenticated() and not self._has_auth_header(request_headers):
            request_headers["Authorization"] = f"Bearer {session.token}"
        has_auth_header = self._has_auth_header(request_headers)
        transport_error_seen = False
        is_paystack_path = _is_payment_reference_path(path)
        ordered_base_urls = self._ordered_base_urls()
        if is_paystack_path:
            # Paystack references must be created, verified, and recovered on
            # the same backend/database. Use the backend that last accepted the
            # current app session so a valid user is not sent to another host
            # and rejected as unauthenticated.
            ordered_base_urls = ordered_base_urls[:1]
            failover = False
        elif not failover:
            ordered_base_urls = ordered_base_urls[:1]
        failover_status_codes = PAYSTACK_FAILOVER_STATUS_CODES if is_paystack_path else FAILOVER_STATUS_CODES

        for index, base_url in enumerate(ordered_base_urls):
            try:
                with self._request_lock:
                    response = self.session.request(
                        method=method.upper(),
                        url=f"{base_url}{path}",
                        json=payload,
                        params=params,
                        headers=request_headers,
                        timeout=_coerce_timeout(timeout),
                    )
                data = self._safe_json(response)
                result = {
                    "ok": response.status_code < 400,
                    "status_code": response.status_code,
                    "data": data,
                }
                if response.status_code < 400:
                    self.base_url = base_url
                    return result
                last_result = result

                if has_auth_header and response.status_code in AUTH_FAILOVER_STATUS_CODES:
                    if transport_error_seen or index > 0:
                        last_result = {
                            "ok": False,
                            "status_code": 0,
                            "data": {
                                "detail": (
                                    "Backend connection failed. Please check your internet connection "
                                    "and try again."
                                )
                            },
                        }
                        continue

                should_failover = response.status_code in failover_status_codes or (
                    has_auth_header and response.status_code in AUTH_FAILOVER_STATUS_CODES
                )
                if not failover or not should_failover:
                    return result
            except Exception as exc:
                transport_error_seen = True
                last_result = {
                    "ok": False,
                    "status_code": 0,
                    "data": {"detail": self._timeout_message(exc)},
                }

        return last_result or {
            "ok": False,
            "status_code": 0,
            "data": {"detail": "Backend connection failed. Please check your internet connection and try again."},
        }

    def warmup(self) -> None:
        self.request("GET", "/health", timeout=FAST_TIMEOUT, failover=False)

    def post(self, path: str, payload: dict, headers: dict | None = None, timeout=DEFAULT_TIMEOUT):
        return self.request("POST", path, payload=payload, headers=headers, timeout=timeout)["data"]

    def get(
        self,
        path: str,
        params: dict | None = None,
        headers: dict | None = None,
        timeout=DEFAULT_TIMEOUT,
    ):
        return self.request("GET", path, params=params, headers=headers, timeout=timeout)

    def put(self, path: str, payload: dict, headers: dict | None = None, timeout=DEFAULT_TIMEOUT):
        return self.request("PUT", path, payload=payload, headers=headers, timeout=timeout)

    def patch(self, path: str, payload: dict, headers: dict | None = None, timeout=DEFAULT_TIMEOUT):
        return self.request("PATCH", path, payload=payload, headers=headers, timeout=timeout)


api_client = APIClient()
