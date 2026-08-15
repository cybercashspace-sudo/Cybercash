from __future__ import annotations

from kivy.properties import ColorProperty, StringProperty
from kivymd.app import MDApp

from api.client import api_client
from core.popup_manager import show_message_dialog
from core.message_sanitizer import extract_backend_message
from core.responsive_screen import ResponsiveScreen
from storage import clear_token, get_token, token_is_expired


AUTH_FAILURE_DETAIL = "Session expired. Please sign in again to continue."


class ActionScreen(ResponsiveScreen):
    feedback_text = StringProperty("")
    feedback_color = ColorProperty([0.74, 0.76, 0.80, 1])

    def _set_feedback(self, message: str, level: str = "info") -> None:
        palette = {
            "info": [0.74, 0.76, 0.80, 1],
            "success": [0.54, 0.82, 0.67, 1],
            "warning": [0.94, 0.79, 0.46, 1],
            "error": [0.96, 0.47, 0.42, 1],
        }
        self.feedback_text = str(message or "").strip()
        self.feedback_color = palette.get(level, palette["info"])

    def _show_popup(self, title: str, message: str, on_close=None) -> None:
        show_message_dialog(
            self,
            title=str(title or "Notice"),
            message=str(message or "").strip() or "Please review this message.",
            close_label="Close",
            on_close=on_close,
        )

    @staticmethod
    def _extract_detail(payload: object) -> str:
        return extract_backend_message(payload)

    @staticmethod
    def _is_auth_failure(status_code: object, payload: object) -> bool:
        try:
            code = int(status_code or 0)
        except Exception:
            code = 0
        if code == 401:
            return True

        detail = extract_backend_message(payload).lower()
        return any(
            marker in detail
            for marker in (
                "not authenticated",
                "invalid token",
                "token expired",
                "session expired",
                "could not validate credentials",
            )
        )

    @staticmethod
    def _clear_saved_session() -> None:
        app = MDApp.get_running_app()
        if app is not None:
            app.access_token = ""
        clear_token()

    def _auth_required_payload(self) -> dict:
        return {"detail": AUTH_FAILURE_DETAIL, "_auth_required": True, "_status_code": 401}

    def _show_auth_required(self, message: str = AUTH_FAILURE_DETAIL) -> None:
        self._clear_saved_session()
        self._set_feedback(message, "warning")

        def _go_login(*_args):
            if self.manager and self.manager.has_screen("login"):
                self.manager.current = "login"

        self._show_popup("Sign In Required", message, on_close=_go_login)

    def _auth_headers(self) -> dict | None:
        app = MDApp.get_running_app()
        token = str(getattr(app, "access_token", "") or "").strip()
        if token and token_is_expired(token):
            self._clear_saved_session()
            return None
        if not token:
            token = get_token().strip()
            if token:
                app.access_token = token
        if not token:
            return None
        return {"Authorization": f"Bearer {token}"}

    def _request(
        self,
        method: str,
        path: str,
        payload: dict | None = None,
        params: dict | None = None,
        *,
        requires_auth: bool = True,
        timeout=None,
        clear_session_on_auth_failure: bool = True,
    ) -> tuple[bool, object]:
        headers = {}
        if requires_auth:
            auth_headers = self._auth_headers()
            if not auth_headers:
                return False, {"detail": "Please sign in to continue.", "_auth_required": True}
            headers.update(auth_headers)

        result = api_client.request(
            method=method,
            path=path,
            payload=payload,
            params=params,
            headers=headers,
            timeout=timeout,
        )
        payload = result.get("data", {})
        status_code = result.get("status_code", 0)
        if isinstance(payload, dict):
            payload.setdefault("_status_code", status_code)
        if requires_auth and self._is_auth_failure(status_code, payload):
            if clear_session_on_auth_failure:
                self._clear_saved_session()
                return False, self._auth_required_payload()
            if isinstance(payload, dict):
                payload["_auth_warning"] = True
            return False, payload
        return bool(result.get("ok")), payload

    def go_back(self) -> None:
        manager = self.manager
        if not manager:
            return

        previous = str(getattr(manager, "previous_screen", "") or "").strip()
        disallow = {"splash"}
        if previous and previous != self.name and previous not in disallow and manager.has_screen(previous):
            app = MDApp.get_running_app()
            if app is not None and hasattr(app, "go_to_screen"):
                app.go_to_screen(previous, fallback="login")
            else:
                manager.current = previous
            return

        app = MDApp.get_running_app()
        token = str(getattr(app, "access_token", "") or "").strip()
        if token and manager.has_screen("home"):
            if app is not None and hasattr(app, "go_to_screen"):
                app.go_to_screen("home", fallback="login")
            else:
                manager.current = "home"
            return
        if manager.has_screen("login"):
            if app is not None and hasattr(app, "go_to_screen"):
                app.go_to_screen("login", fallback="")
            else:
                manager.current = "login"
