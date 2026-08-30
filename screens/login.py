from __future__ import annotations

from pathlib import Path
from threading import Thread

from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import BooleanProperty
from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from core.message_sanitizer import extract_backend_message
from core.session import session
from components.app_snackbar import show_app_snackbar
from features.auth.auth_controller import AuthController


class LoginScreen(MDScreen):
    password_visible = BooleanProperty(False)
    loading = BooleanProperty(False)
    remember_me = BooleanProperty(True)
    agent_mode = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.controller = AuthController()

    def on_pre_enter(self, *_args):
        self.remember_me = True
        self.password_visible = False
        self.agent_mode = False
        self._set_text("", "momo_input", "username", "identifier", "pin_input", "password")
        self._restore_remembered_identity()
        self._sync_auth_controls()

    def on_enter(self):
        self.start_animation()

    def start_animation(self, *_args):
        return

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
        self._set_text(identifier, "momo_input", "username", "identifier")

    def _sync_auth_controls(self) -> None:
        password_toggle = self.ids.get("password_toggle")
        if password_toggle is not None:
            if hasattr(password_toggle, "visible"):
                password_toggle.visible = self.password_visible
            elif hasattr(password_toggle, "icon"):
                password_toggle.icon = "eye" if self.password_visible else "eye-off"

        remember_toggle = self.ids.get("remember_toggle")
        if remember_toggle is not None:
            if hasattr(remember_toggle, "checked"):
                remember_toggle.checked = self.remember_me
            elif hasattr(remember_toggle, "active"):
                remember_toggle.active = self.remember_me

        agent_toggle = self.ids.get("agent_toggle")
        if agent_toggle is not None:
            if hasattr(agent_toggle, "checked"):
                agent_toggle.checked = self.agent_mode
            elif hasattr(agent_toggle, "active"):
                agent_toggle.active = self.agent_mode

    def toggle_password(self):
        self.password_visible = not self.password_visible
        password = self.ids.get("pin_input") or self.ids.get("password")
        if password is not None:
            password.password = not self.password_visible
        self._sync_auth_controls()

    def toggle_agent_mode(self, *args):
        active = False
        for value in reversed(args):
            if isinstance(value, bool):
                active = value
                break
            if hasattr(value, "active"):
                active = bool(getattr(value, "active"))
                break
        self.agent_mode = bool(active)
        self._sync_auth_controls()

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
        self._sync_auth_controls()

    def login(self):
        if self.loading:
            return

        momo_number = self._get_text("momo_input", "username", "identifier")
        pin = self._get_text("pin_input", "password")

        if momo_number == "":
            self.show_message("Please enter your MoMo number.")
            return

        if pin == "":
            self.show_message("Please enter your PIN.")
            return

        self._set_loading(True)
        Thread(
            target=self._login_worker,
            args=(momo_number, pin, self.agent_mode),
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

    def _login_worker(self, momo_number: str, pin: str, is_agent: bool) -> None:
        try:
            result = self.controller.login(momo_number, pin, is_agent=is_agent)
        except Exception as exc:
            message = extract_backend_message(
                exc,
                fallback="Login failed. Please try again.",
            )
            Clock.schedule_once(lambda _dt, msg=message: self._finish_login_failure(msg))
            return

        Clock.schedule_once(
            lambda _dt, res=result, momo=momo_number: self._apply_login_response(
                momo,
                res,
            )
        )

    def _finish_login_failure(self, message: str) -> None:
        self._set_loading(False)
        self.show_message(message)

    def _apply_login_response(self, momo_number: str, result: dict) -> None:
        try:
            if not isinstance(result, dict):
                self.show_message("Unable to sign in right now.")
                return

            status = str(result.get("status", "") or "").strip().lower()

            if status in {"verify_required", "verification_required", "registered"}:
                app = MDApp.get_running_app()
                if app is not None:
                    app.pending_momo = momo_number
                self.show_message("Verify your account to continue.")
                self._go_to_screen("otp", fallback="login")
                return

            if status == "pending_kyc":
                self.show_message("Your agent onboarding is pending KYC approval.")
                return

            token = str(result.get("access_token", "") or "").strip()
            if token:
                if self.remember_me:
                    self._save_remember_me(momo_number, result)
                else:
                    try:
                        session.clear_remember_me()
                    except Exception:
                        pass
                self.show_message("Login successful.")
                app = MDApp.get_running_app()
                target_screen = "admin_dashboard" if app is not None and bool(getattr(app, "is_admin", False)) else "home"
                self._go_to_screen(target_screen, fallback="login")
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

    def _save_remember_me(self, momo_number: str, result: dict) -> None:
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
            session.set_remember_me(momo_number, first_name=first_name, pin="1")
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


_LOGIN_KV = str(Path(__file__).with_name("login.kv"))
_LOADED_KV_FILES = list(getattr(Builder, "files", []) or [])
if _LOGIN_KV not in _LOADED_KV_FILES:
    Builder.load_file(_LOGIN_KV)
