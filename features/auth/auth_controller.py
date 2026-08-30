from __future__ import annotations

from kivy.app import App
from kivymd.app import MDApp

from api.client import FAST_TIMEOUT, api_client
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
    def _response_data(response: dict | None) -> dict:
        if isinstance(response, dict):
            data = response.get("data")
            if isinstance(data, dict):
                return dict(data)
        return {}

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
            auth_headers = {"Authorization": f"Bearer {token}"}
            profile_payload = dict(user_payload or {})
            current_role = str(profile_payload.get("role") or result.get("role") or "").strip().lower()
            if not current_role or (not profile_payload.get("is_admin") and not profile_payload.get("is_agent")):
                try:
                    me_response = api_client.get("/auth/me", headers=auth_headers, timeout=FAST_TIMEOUT)
                    me_payload = self._response_data(me_response)
                    if me_payload:
                        profile_payload = {**profile_payload, **me_payload}
                        current_role = str(profile_payload.get("role") or current_role).strip().lower()
                except Exception:
                    pass
                if (
                    not profile_payload.get("is_admin")
                    and not profile_payload.get("is_agent")
                    and current_role not in {"admin", "super_admin", "agent"}
                ):
                    try:
                        agent_response = api_client.get("/agents/me", headers=auth_headers, timeout=FAST_TIMEOUT)
                        agent_payload = self._response_data(agent_response)
                        if agent_payload:
                            profile_payload = {**profile_payload, **agent_payload}
                            current_role = str(profile_payload.get("role") or current_role).strip().lower()
                    except Exception:
                        pass

            is_admin = bool(
                profile_payload.get("is_admin")
                or current_role in {"admin", "super_admin"}
            )
            is_agent = bool(
                profile_payload.get("is_agent")
                or profile_payload.get("agent_active")
                or current_role == "agent"
            )
            resolved_role = current_role or ("admin" if is_admin else "agent" if is_agent else "")
            if resolved_role:
                profile_payload["role"] = resolved_role
            profile_payload["is_admin"] = is_admin
            profile_payload["is_agent"] = is_agent
            profile_payload["agent_active"] = is_agent

            session.save(
                token,
                user=profile_payload or user_payload,
                refresh_token=str(result.get("refresh_token", "") or "").strip(),
            )
            if profile_payload:
                try:
                    session.set_user(profile_payload)
                except Exception:
                    pass

            app = MDApp.get_running_app()
            if app is not None:
                app.access_token = token
                app.user_name = str(
                    profile_payload.get("name")
                    or result.get("first_name")
                    or profile_payload.get("full_name")
                    or profile_payload.get("first_name")
                    or app.user_name
                    or ""
                ).strip() or app.user_name
                app.is_admin = is_admin
                app.is_agent_active = is_agent
                app.user_role = resolved_role or ("admin" if is_admin else "agent" if is_agent else "user")
                app.pending_momo = ""

                app_state = getattr(app, "app_state", None)
                if isinstance(app_state, AppState):
                    app_state.set_user(profile_payload or user_payload or {"identifier": momo_number, "name": app.user_name})
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
            self.apply_login_result(result, momo_number=momo_number)

        if not token and status not in {"verify_required", "verification_required", "registered", "pending_kyc"}:
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
