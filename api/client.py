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
load_dotenv(os.path.join(project_root, ".env"))
load_dotenv()

try:
    from kivy.utils import platform as kivy_platform
except Exception:
    kivy_platform = ""

MOBILE_BACKEND_URL = "https://www.cybercash.space"
DEFAULT_CONNECT_TIMEOUT_SECONDS = 8
DEFAULT_READ_TIMEOUT_SECONDS = 45
DEFAULT_TIMEOUT = (DEFAULT_CONNECT_TIMEOUT_SECONDS, DEFAULT_READ_TIMEOUT_SECONDS)
RETRY_STATUS_CODES = (429, 500, 502, 503, 504)


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

    return DEFAULT_API_URL


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
        try:
            response = self.session.request(
                method=method.upper(),
                url=f"{self.base_url}{path}",
                json=payload,
                params=params,
                headers=headers or {},
                timeout=_coerce_timeout(timeout),
            )
            data = self._safe_json(response)
            return {
                "ok": response.status_code < 400,
                "status_code": response.status_code,
                "data": data,
            }
        except Exception as exc:
            return {
                "ok": False,
                "status_code": 0,
                "data": {"detail": self._timeout_message(exc)},
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
