from __future__ import annotations

from kivy.app import App
from kivymd.app import MDApp

from core.app_state import AppState
from core.exceptions import AuthenticationError, ValidationError
from core.session import session
from features.auth.auth_service import AuthService
from features.auth.validators import validate_pin
from utils.network import normalize_ghana_number


class AuthController:
    def __init__(self, service: AuthService | None = None):
        self.service = service or AuthService()

    @staticmethod
    def _normalize_momo_number(value: str) -> str:
        momo = normalize_ghana_number(value)
        digits = "".join(ch for ch in momo if ch.isdigit())
        if len(digits) != 10 or not digits.startswith("0"):
            raise ValidationError("Enter a valid MoMo number.")
        return digits

    def apply_login_result(self, result: dict, momo_number: str = ""):
        if not isinstance(result, dict):
            raise AuthenticationError("Unexpected login response.")

        token = str(result.get("access_token", "") or "").strip()
        user_payload = result.get("user") if isinstance(result.get("user"), dict) else {}

        if token:
            session.save(
                token,
                user=user_payload,
                refresh_token=str(result.get("refresh_token", "") or "").strip(),
            )

            app = MDApp.get_running_app()
            if app is not None:
                role = str(
                    user_payload.get("role")
                    or result.get("role")
                    or ""
                ).strip().lower()
                is_admin = bool(user_payload.get("is_admin") or role in {"admin", "super_admin"})
                is_agent = bool(user_payload.get("is_agent") or role == "agent")
                app.access_token = token
                app.user_name = str(
                    user_payload.get("name")
                    or result.get("first_name")
                    or user_payload.get("full_name")
                    or app.user_name
                    or ""
                ).strip() or app.user_name
                app.is_admin = is_admin
                app.is_agent_active = is_agent
                app.user_role = role or ("admin" if is_admin else "agent" if is_agent else "user")
                app.pending_momo = ""

                app_state = getattr(app, "app_state", None)
                if isinstance(app_state, AppState):
                    app_state.set_user(user_payload or {"identifier": momo_number, "name": app.user_name})
                if hasattr(app, "start_background_services"):
                    try:
                        app.start_background_services()
                    except Exception:
                        pass

        return result

    def login(self, momo_number: str, pin: str, is_agent: bool = False):
        momo_number = self._normalize_momo_number(momo_number)
        pin = validate_pin(pin)

        result = self.service.login(momo_number, pin, is_agent=is_agent)
        if not isinstance(result, dict):
            raise AuthenticationError("Unexpected login response.")

        token = str(result.get("access_token", "") or "").strip()
        status = str(result.get("status", "") or "").strip().lower()

        if token:
            self.apply_login_result(result, identifier=momo_number)

        if not token and status not in {"verify_required", "verification_required"}:
            raise AuthenticationError("Token missing from login response.")

        return result

    def logout(self):
        session.clear_auth()
        app = MDApp.get_running_app()
        if app is not None:
            reset_session = getattr(app, "reset_session_state", None)
            if callable(reset_session):
                reset_session(clear_wallet_state=True)
                return
            app.access_token = ""
            app.pending_momo = ""
            app.user_name = "Cyber Cash User"
            if hasattr(app, "stop_background_services"):
                try:
                    app.stop_background_services()
                except Exception:
                    pass
            app_state = getattr(app, "app_state", None)
            if isinstance(app_state, AppState):
                app_state.reset()
