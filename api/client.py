import os
import json
import threading

import requests
from requests.adapters import HTTPAdapter

from core.message_sanitizer import sanitize_backend_message

try:
    from urllib3.util.retry import Retry
except Exception:
    Retry = None

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*_args, **_kwargs):
        return False


project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

try:
    from kivy.utils import platform as kivy_platform
except Exception:
    kivy_platform = ""


def _safe_load_dotenv(path: str) -> None:
    try:
        load_dotenv(path)
    except Exception:
        pass


def _is_runtime_mobile_platform() -> bool:
    return str(kivy_platform or "").strip().lower() in {"android", "ios"}


# Keep secrets out of packaged mobile apps. Android/iOS should use app_config.json
# or built-in defaults for the backend URL; Paystack keys belong on the backend.
if not _is_runtime_mobile_platform():
    _safe_load_dotenv(os.path.join(project_root, ".env"))

MOBILE_BACKEND_URL = "cybercash.space"
MOBILE_BACKEND_FALLBACK_URLS = (
    "www.cybercash.space",
    "https://cyber-cash.onrender.com",
)
DEFAULT_CONNECT_TIMEOUT_SECONDS = 4
DEFAULT_READ_TIMEOUT_SECONDS = 12
DEFAULT_TIMEOUT = (DEFAULT_CONNECT_TIMEOUT_SECONDS, DEFAULT_READ_TIMEOUT_SECONDS)
FAST_TIMEOUT = (2, 6)
RETRY_STATUS_CODES = (429, 500, 502, 503, 504)
FAILOVER_STATUS_CODES = (502, 503, 504)
PAYSTACK_FAILOVER_STATUS_CODES = (500, 502, 503, 504)
AUTH_FAILOVER_STATUS_CODES = (401, 403)


def _normalize_api_url(raw_value: str) -> str:
    cleaned_value = str(raw_value or "").strip().rstrip("/")
    if not cleaned_value:
        return ""
    if "://" not in cleaned_value:
        cleaned_value = f"https://{cleaned_value}"
    return cleaned_value


def _is_mobile_platform() -> bool:
    return _is_runtime_mobile_platform()


def _is_payment_reference_path(path: str) -> bool:
    lower_path = str(path or "").lower()
    if lower_path.startswith("/paystack/") or "/paystack/" in lower_path:
        return True
    if lower_path.startswith("/api/paystack/") or "/api/paystack/" in lower_path:
        return True
    if lower_path.startswith("/api/wallet/topup/paystack/"):
        return True
    return lower_path == "/agents/register" or lower_path.startswith("/agents/register/")


def _default_api_url() -> str:
    """Default API URL when no env var or app_config.json override is provided.

    - Desktop dev: use localhost backend.
    - Android/iOS: avoid 127.0.0.1 (phone != your PC).
    """

    if _is_mobile_platform():
        return MOBILE_BACKEND_URL
    return "http://127.0.0.1:8000"


DEFAULT_API_URL = _default_api_url()


def _load_app_config() -> dict:
    candidates = [
        os.path.join(project_root, "app_config.json"),
        os.path.join(os.getcwd(), "app_config.json"),
    ]

    for path in candidates:
        if not path or not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            return payload if isinstance(payload, dict) else {}
        except Exception:
            continue

    return {}


def resolve_api_url() -> str:
    for env_name in ("KIVY_API_URL", "CYBERCASH_API_URL", "BACKEND_URL"):
        value = _normalize_api_url(os.getenv(env_name, ""))
        if value:
            return value

    config = _load_app_config()
    value = _normalize_api_url(config.get("api_url", ""))
    if value:
        return value

    return _normalize_api_url(DEFAULT_API_URL)


def resolve_api_urls() -> list[str]:
    urls = []
    for value in (resolve_api_url(), *MOBILE_BACKEND_FALLBACK_URLS):
        normalized = _normalize_api_url(value)
        if normalized and normalized not in urls:
            urls.append(normalized)
    return urls


def _coerce_timeout(timeout):
    if timeout is None:
        return DEFAULT_TIMEOUT
    if isinstance(timeout, (tuple, list)) and len(timeout) == 2:
        return float(timeout[0]), float(timeout[1])
    return DEFAULT_CONNECT_TIMEOUT_SECONDS, float(timeout)


API_URL = resolve_api_url()


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
        request_headers = headers or {}
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
