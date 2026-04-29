from __future__ import annotations

from kivy.properties import ColorProperty, StringProperty
from kivymd.app import MDApp

from api.client import api_client
from core.popup_manager import show_message_dialog
from core.message_sanitizer import extract_backend_message
from core.responsive_screen import ResponsiveScreen
from storage import get_token


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

    def _auth_headers(self) -> dict | None:
        app = MDApp.get_running_app()
        token = str(getattr(app, "access_token", "") or "").strip()
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
    ) -> tuple[bool, object]:
        headers = {}
        if requires_auth:
            auth_headers = self._auth_headers()
            if not auth_headers:
                return False, {"detail": "Please sign in to continue."}
            headers.update(auth_headers)

        result = api_client.request(
            method=method,
            path=path,
            payload=payload,
            params=params,
            headers=headers,
        )
        return bool(result.get("ok")), result.get("data", {})

    def go_back(self) -> None:
        manager = self.manager
        if not manager:
            return

        previous = str(getattr(manager, "previous_screen", "") or "").strip()
        disallow = {"splash"}
        if previous and previous != self.name and previous not in disallow and manager.has_screen(previous):
            manager.current = previous
            return

        app = MDApp.get_running_app()
        token = str(getattr(app, "access_token", "") or "").strip()
        if token and manager.has_screen("dashboard"):
            manager.current = "dashboard"
            return
        if manager.has_screen("login"):
            manager.current = "login"
