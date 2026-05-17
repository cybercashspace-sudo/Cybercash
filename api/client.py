import os
import json

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


def _safe_load_dotenv(path: str) -> None:
    try:
        load_dotenv(path)
    except Exception:
        pass


_safe_load_dotenv(os.path.join(project_root, ".env"))

try:
    from kivy.utils import platform as kivy_platform
except Exception:
    kivy_platform = ""

MOBILE_BACKEND_URL = "www.cybercash.space"
MOBILE_BACKEND_FALLBACK_URLS = (
    "cybercash.space",
    "https://cyber-cash.onrender.com",
)
DEFAULT_CONNECT_TIMEOUT_SECONDS = 8
DEFAULT_READ_TIMEOUT_SECONDS = 45
DEFAULT_TIMEOUT = (DEFAULT_CONNECT_TIMEOUT_SECONDS, DEFAULT_READ_TIMEOUT_SECONDS)
RETRY_STATUS_CODES = (429, 500, 502, 503, 504)
FAILOVER_STATUS_CODES = (502, 503, 504)


def _normalize_api_url(raw_value: str) -> str:
    cleaned_value = str(raw_value or "").strip().rstrip("/")
    if not cleaned_value:
        return ""
    if "://" not in cleaned_value:
        cleaned_value = f"https://{cleaned_value}"
    return cleaned_value


def _is_mobile_platform() -> bool:
    return str(kivy_platform or "").strip().lower() in {"android", "ios"}


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
        self._install_retries()

    def _install_retries(self) -> None:
        if Retry is None:
            return

        retry = Retry(
            total=2,
            connect=2,
            read=1,
            status=2,
            backoff_factor=0.6,
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

    def request(
        self,
        method: str,
        path: str,
        payload: dict | None = None,
        params: dict | None = None,
        headers: dict | None = None,
        timeout=DEFAULT_TIMEOUT,
    ) -> dict:
        last_result = None
        for base_url in self.base_urls:
            try:
                response = self.session.request(
                    method=method.upper(),
                    url=f"{base_url}{path}",
                    json=payload,
                    params=params,
                    headers=headers or {},
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
                if response.status_code not in FAILOVER_STATUS_CODES:
                    return result
            except Exception as exc:
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
        self.request("GET", "/health", timeout=(5, 20))

    def post(self, path: str, payload: dict, headers: dict | None = None):
        return self.request("POST", path, payload=payload, headers=headers)["data"]

    def get(self, path: str, params: dict | None = None, headers: dict | None = None):
        return self.request("GET", path, params=params, headers=headers)

    def put(self, path: str, payload: dict, headers: dict | None = None):
        return self.request("PUT", path, payload=payload, headers=headers)

    def patch(self, path: str, payload: dict, headers: dict | None = None):
        return self.request("PATCH", path, payload=payload, headers=headers)


api_client = APIClient()
