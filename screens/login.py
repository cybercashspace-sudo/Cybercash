from __future__ import annotations

from pathlib import Path
from threading import Thread

from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import BooleanProperty
from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from core.exceptions import AuthenticationError, ValidationError
from core.message_sanitizer import extract_backend_message
from core.session import session
from components.app_snackbar import show_app_snackbar
from features.auth.auth_controller import AuthController
from features.auth.validators import validate_identifier, validate_password


class LoginScreen(MDScreen):
    password_visible = BooleanProperty(False)
    loading = BooleanProperty(False)
    remember_me = BooleanProperty(True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.controller = AuthController()

    def on_pre_enter(self, *_args):
        self.remember_me = True
        self._set_text("", "username", "identifier", "password")
        self._restore_remembered_identity()

    def on_enter(self):
        self.start_animation()

    def start_animation(self, *_args):
        for name in ("brand_block", "login_card", "field_stack", "action_stack"):
            widget = self.ids.get(name)
            if widget is not None:
                widget.opacity = 1

    def _get_text(self, *names: str) -> str:
        for name in names:
            widget = self.ids.get(name)
            if widget is None:
                continue
            value = getattr(widget, "text", "")
            if value is not None:
                return str(value).strip()
        return ""

    def _set_text(self, value: str, *names: str) -> None:
        for name in names:
            widget = self.ids.get(name)
            if widget is None or not hasattr(widget, "text"):
                continue
            widget.text = str(value or "")
            return

    def _restore_remembered_identity(self) -> None:
        try:
            remembered = session.get_remember_me() or {}
        except Exception:
            remembered = {}

        identifier = str(remembered.get("momo") or "").strip()
        if not identifier:
            return

        self.remember_me = True
        self._set_text(identifier, "username", "identifier")

    def toggle_password(self):
        self.password_visible = not self.password_visible
        password = self.ids.get("password")
        if password is not None:
            password.password = not self.password_visible
        eye = self.ids.get("password_toggle") or self.ids.get("eye_icon")
        if eye is not None:
            eye.icon = "eye-off" if self.password_visible else "eye"

    def toggle_remember(self, *args):
        active = False
        for value in reversed(args):
            if isinstance(value, bool):
                active = value
                break
            if hasattr(value, "active"):
                active = bool(getattr(value, "active"))
                break
        self.remember_me = bool(active)
        if not self.remember_me:
            try:
                session.clear_remember_me()
            except Exception:
                pass

    def login(self):
        if self.loading:
            return

        username = self._get_text("username", "identifier")
        password = self._get_text("password")

        if username == "":
            self.show_message("Please enter username.")
            return

        if password == "":
            self.show_message("Please enter password.")
            return

        try:
            validate_identifier(username)
            validate_password(password)
        except (AuthenticationError, ValidationError) as exc:
            self.show_message(str(exc))
            return

        self._set_loading(True)
        Thread(
            target=self._login_worker,
            args=(username, password),
            daemon=True,
        ).start()

    def login_user(self):
        self.login()

    def _set_loading(self, value: bool) -> None:
        self.loading = bool(value)
        button = self.ids.get("login_button")
        if button is not None:
            if hasattr(button, "loading"):
                button.loading = bool(value)
            else:
                button.disabled = bool(value)

    def _login_worker(self, identifier: str, password: str) -> None:
        try:
            result = self.controller.service.login(identifier, password)
        except Exception as exc:
            message = extract_backend_message(
                exc,
                fallback="Login failed. Please try again.",
            )
            Clock.schedule_once(lambda _dt, msg=message: self._finish_login_failure(msg))
            return

        Clock.schedule_once(
            lambda _dt, res=result, ident=identifier: self._apply_login_response(
                ident,
                res,
            )
        )

    def _finish_login_failure(self, message: str) -> None:
        self._set_loading(False)
        self.show_message(message)

    def _apply_login_response(self, identifier: str, result: dict) -> None:
        try:
            if not isinstance(result, dict):
                self.show_message("Unable to sign in right now.")
                return

            status = str(result.get("status", "") or "").strip().lower()

            if status in {"verify_required", "verification_required", "registered"}:
                app = MDApp.get_running_app()
                if app is not None:
                    app.pending_momo = identifier
                self.show_message("Verify your account to continue.")
                self._go_to_screen("otp", fallback="login")
                return

            if status == "pending_kyc":
                self.show_message("Your agent onboarding is pending KYC approval.")
                return

            token = str(result.get("access_token", "") or "").strip()
            if token:
                self.controller.apply_login_result(result, identifier=identifier)
                if self.remember_me:
                    self._save_remember_me(identifier, result)
                else:
                    try:
                        session.clear_remember_me()
                    except Exception:
                        pass
                self.show_message("Login successful.")
                self._go_to_screen("home", fallback="login")
                return

            detail = extract_backend_message(
                result,
                fallback="Unable to sign in right now.",
            )
            self.show_message(detail)
        except Exception:
            self.show_message("Login failed. Please try again.")
        finally:
            self._set_loading(False)

    def _save_remember_me(self, identifier: str, result: dict) -> None:
        first_name = ""
        if isinstance(result, dict):
            user = result.get("user")
            if isinstance(user, dict):
                first_name = str(
                    user.get("first_name")
                    or user.get("name")
                    or user.get("full_name")
                    or ""
                ).strip()
            if not first_name:
                first_name = str(result.get("first_name") or "").strip()

        try:
            # The app only needs a truthy marker to restore the biometric prompt flow.
            session.set_remember_me(identifier, first_name=first_name, pin="1")
        except Exception:
            pass

    def _go_to_screen(self, screen_name: str, fallback: str = "login") -> bool:
        app = MDApp.get_running_app()
        if app is not None and hasattr(app, "go_to_screen"):
            app.go_to_screen(screen_name, fallback=fallback)
            return True

        if self.manager is not None and self.manager.has_screen(screen_name):
            self.manager.current = screen_name
            return True

        return False

    def forgot_password(self):
        if self._go_to_screen("reset_pin", fallback="login"):
            return
        self.show_message("Forgot Password")

    def forgot_pin(self):
        self.forgot_password()

    def signup(self):
        if self._go_to_screen("register", fallback="login"):
            return
        self.show_message("Navigate to Sign Up")

    def google_login(self):
        self.show_message("Google Login")

    def facebook_login(self):
        self.show_message("Facebook Login")

    def apple_login(self):
        self.show_message("Apple Login")

    def phone_login(self):
        self.show_message("Phone Login")

    def biometric_login(self):
        app = MDApp.get_running_app()
        if app is not None and getattr(app, "access_token", ""):
            self._go_to_screen("home", fallback="login")
            return
        self.show_message("Use your saved session to continue.")

    def show_message(self, text):
        show_app_snackbar(text)


Builder.load_file(str(Path(__file__).with_name("login.kv")))
