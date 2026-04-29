import os
import json

import requests

from core.message_sanitizer import sanitize_backend_message

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


def _normalize_api_url(raw_value: str) -> str:
    cleaned_value = str(raw_value or "").strip().rstrip("/")
    if not cleaned_value:
        return ""
    if "://" not in cleaned_value:
        cleaned_value = f"https://{cleaned_value}"
    return cleaned_value


def _default_api_url() -> str:
    """Default API URL when no env var or app_config.json override is provided.

    - Desktop dev: use localhost backend.
    - Android/iOS: avoid 127.0.0.1 (phone != your PC).
    """

    platform_name = str(kivy_platform or "").strip().lower()
    if platform_name in {"android", "ios"}:
        return "https://cybercash.space"
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


API_URL = resolve_api_url()


class APIClient:
    def __init__(self, base_url: str | None = None):
        self.base_url = str(base_url or API_URL).rstrip("/")

    @staticmethod
    def _safe_json(response):
        try:
            return response.json() if response.content else {}
        except Exception:
            text = (response.text or "").strip()
            return {"detail": sanitize_backend_message(text or f"HTTP {response.status_code}")}

    def request(
        self,
        method: str,
        path: str,
        payload: dict | None = None,
        params: dict | None = None,
        headers: dict | None = None,
        timeout: int = 12,
    ) -> dict:
        try:
            response = requests.request(
                method=method.upper(),
                url=f"{self.base_url}{path}",
                json=payload,
                params=params,
                headers=headers or {},
                timeout=timeout,
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
                "data": {"detail": sanitize_backend_message(exc)},
            }

    def post(self, path: str, payload: dict, headers: dict | None = None):
        try:
            response = requests.post(
                f"{self.base_url}{path}",
                json=payload,
                headers=headers or {},
                timeout=12,
            )
            return self._safe_json(response)
        except Exception as exc:
            return {"detail": sanitize_backend_message(exc)}

    def get(self, path: str, params: dict | None = None, headers: dict | None = None):
        return self.request("GET", path, params=params, headers=headers)

    def put(self, path: str, payload: dict, headers: dict | None = None):
        return self.request("PUT", path, payload=payload, headers=headers)

    def patch(self, path: str, payload: dict, headers: dict | None = None):
        return self.request("PATCH", path, payload=payload, headers=headers)


api_client = APIClient()
