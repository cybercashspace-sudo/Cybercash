from __future__ import annotations

from kivy.app import App
from kivymd.app import MDApp

from core.app_state import AppState
from core.exceptions import AuthenticationError
from core.session import session
from features.auth.auth_service import AuthService
from features.auth.validators import validate_identifier, validate_password


class AuthController:
    def __init__(self, service: AuthService | None = None):
        self.service = service or AuthService()

    def apply_login_result(self, result: dict, identifier: str = ""):
        if not isinstance(result, dict):
            raise AuthenticationError("Unexpected login response.")

        token = str(result.get("access_token", "") or "").strip()
        user_payload = result.get("user") if isinstance(result.get("user"), dict) else {}

        if token:
            session.save(token, user=user_payload)
            session.set_user(user_payload)

            app = MDApp.get_running_app()
            if app is not None:
                app.access_token = token
                app.user_name = str(
                    user_payload.get("name")
                    or result.get("first_name")
                    or user_payload.get("full_name")
                    or app.user_name
                    or ""
                ).strip() or app.user_name
                app.pending_momo = ""

                app_state = getattr(app, "app_state", None)
                if isinstance(app_state, AppState):
                    app_state.set_user(user_payload or {"identifier": identifier, "name": app.user_name})

        return result

    def login(self, identifier: str, password: str, is_agent: bool = False):
        identifier = validate_identifier(identifier)
        password = validate_password(password)

        result = self.service.login(identifier, password, is_agent=is_agent)
        if not isinstance(result, dict):
            raise AuthenticationError("Unexpected login response.")

        token = str(result.get("access_token", "") or "").strip()
        status = str(result.get("status", "") or "").strip().lower()

        if token:
            self.apply_login_result(result, identifier=identifier)

        if not token and status not in {"verify_required", "verification_required"}:
            raise AuthenticationError("Token missing from login response.")

        return result

    def logout(self):
        session.save("")
        session.set_user(None)
        app = MDApp.get_running_app()
        if app is not None:
            app.access_token = ""
            app.pending_momo = ""
            app.user_name = "Cyber Cash User"
            app_state = getattr(app, "app_state", None)
            if isinstance(app_state, AppState):
                app_state.reset()
