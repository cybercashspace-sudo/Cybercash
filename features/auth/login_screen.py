from __future__ import annotations

from threading import Thread

from kivy.clock import Clock
from kivy.properties import BooleanProperty
from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivymd.uix.snackbar import MDSnackbar, MDSnackbarText

from core.exceptions import AuthenticationError, ValidationError
from core.message_sanitizer import extract_backend_message
from features.auth.animations import AuthAnimations
from features.auth.auth_controller import AuthController
from features.auth.validators import validate_identifier, validate_password


class LoginScreen(MDScreen):
    password_visible = BooleanProperty(False)
    loading = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.controller = AuthController()

    def on_enter(self):
        Clock.schedule_once(self.start_animation, 0.08)

    def start_animation(self, *_args):
        AuthAnimations.enter(self.ids.get("brand_block"), 0.00, 0.35)
        AuthAnimations.slide(self.ids.get("login_card"), 0.15, 28, 0.45)
        AuthAnimations.enter(self.ids.get("field_stack"), 0.30, 0.30)
        AuthAnimations.enter(self.ids.get("action_stack"), 0.45, 0.30)

    def toggle_password(self):
        self.password_visible = not self.password_visible
        password = self.ids.get("password")
        if password is not None:
            password.password = not self.password_visible
        eye = self.ids.get("password_toggle")
        if eye is not None:
            eye.icon = "eye-off" if self.password_visible else "eye"

    def login_user(self):
        if self.loading:
            return

        identifier = str(self.ids.identifier.text or "").strip()
        password = str(self.ids.password.text or "").strip()

        try:
            validate_identifier(identifier)
            validate_password(password)
        except (AuthenticationError, ValidationError) as exc:
            self.show_message(str(exc))
            return

        self._set_loading(True)
        Thread(target=self._login_worker, args=(identifier, password), daemon=True).start()

    def _set_loading(self, value: bool) -> None:
        self.loading = bool(value)
        button = self.ids.get("login_button")
        if button is not None:
            button.loading = bool(value)

    def _login_worker(self, identifier: str, password: str) -> None:
        try:
            result = self.controller.service.login(identifier, password)
        except Exception as exc:
            message = extract_backend_message(exc, fallback="Login failed. Please try again.")
            Clock.schedule_once(lambda _dt, msg=message: self._finish_login_failure(msg))
            return

        Clock.schedule_once(lambda _dt, res=result, ident=identifier: self._apply_login_response(ident, res))

    def _finish_login_failure(self, message: str) -> None:
        self._set_loading(False)
        self.show_message(message)

    def _apply_login_response(self, identifier: str, result: dict) -> None:
        try:
            status = str(result.get("status", "") or "").strip().lower() if isinstance(result, dict) else ""

            if status in {"verify_required", "verification_required", "registered"}:
                app = MDApp.get_running_app()
                if app is not None:
                    app.pending_momo = identifier
                self.show_message("Verify your account to continue.")
                if app is not None and hasattr(app, "go_to_screen"):
                    app.go_to_screen("otp", fallback="login")
                elif self.manager is not None and self.manager.has_screen("otp"):
                    self.manager.current = "otp"
                return

            if status == "pending_kyc":
                self.show_message("Your agent onboarding is pending KYC approval.")
                return

            token = str(result.get("access_token", "") or "").strip() if isinstance(result, dict) else ""
            if token:
                self.controller.apply_login_result(result, identifier=identifier)
                app = MDApp.get_running_app()
                if app is not None and hasattr(app, "go_to_screen"):
                    app.go_to_screen("home", fallback="login")
                elif self.manager is not None and self.manager.has_screen("home"):
                    self.manager.current = "home"
                self.show_message("Login successful.")
                return

            detail = extract_backend_message(result, fallback="Unable to sign in right now.")
            self.show_message(detail)
        except Exception:
            self.show_message("Login failed. Please try again.")
        finally:
            self._set_loading(False)

    def forgot_pin(self):
        app = MDApp.get_running_app()
        if app is not None and hasattr(app, "go_to_screen") and self.manager and self.manager.has_screen("reset_pin"):
            app.go_to_screen("reset_pin", fallback="login")
            return
        self.show_message("Forgot PIN")

    def signup(self):
        app = MDApp.get_running_app()
        if app is not None and hasattr(app, "go_to_screen") and self.manager and self.manager.has_screen("register"):
            app.go_to_screen("register", fallback="login")
            return
        self.show_message("Create account")

    def biometric_login(self):
        app = MDApp.get_running_app()
        if app is not None and getattr(app, "access_token", ""):
            app.go_to_screen("home", fallback="login")
            return
        self.show_message("Use your saved session to continue.")

    def show_message(self, text: str):
        MDSnackbar(MDSnackbarText(text=str(text or ""))).open()
