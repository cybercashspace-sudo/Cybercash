from __future__ import annotations

from pathlib import Path
from threading import Thread

from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import BooleanProperty, ColorProperty, StringProperty
from kivymd.app import MDApp
from core.message_sanitizer import extract_backend_message
from core.navigation import navigate
from core.session import session
from components.app_snackbar import show_app_snackbar
from api.auth import lookup_registered_name
from features.auth.auth_controller import AuthController
from core.responsive_screen import ResponsiveScreen
from utils.network import detect_network, normalize_ghana_number


class LoginScreen(ResponsiveScreen):
    password_visible = BooleanProperty(False)
    loading = BooleanProperty(False)
    remember_me = BooleanProperty(True)
    network_text = StringProperty("Network: Enter your Ghana MoMo number to detect your network.")
    name_hint_text = StringProperty("We will confirm your saved profile name automatically if this number is already registered.")
    detected_first_name = StringProperty("")
    feedback_text = StringProperty("")
    feedback_color = ColorProperty((0.74, 0.76, 0.80, 1))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.controller = AuthController()
        self._lookup_event = None
        self._lookup_seq = 0
        self._login_generation = 0
        self._login_inflight = False
        self._active = False
        self._syncing_momo_input = False

    def on_leave(self, *_args):
        if self._lookup_event is not None:
            self._lookup_event.cancel()
            self._lookup_event = None
        self._lookup_seq += 1
        self._active = False
        self._login_generation += 1
        self._set_loading(False)
        self._set_text("", "pin_input")
        parent_on_leave = getattr(super(), "on_leave", None)
        if callable(parent_on_leave):
            return parent_on_leave(*_args)

    def on_pre_enter(self, *_args):
        self._active = True
        self._login_generation += 1
        self.remember_me = True
        self.password_visible = False
        self._set_text("", "momo_input", "pin_input", "first_name_input")
        self._restore_remembered_identity()
        pin_input = self.ids.get("pin_input")
        if pin_input is not None and hasattr(pin_input, "password"):
            pin_input.password = True
        if pin_input is not None and hasattr(pin_input, "password_visible"):
            pin_input.password_visible = False
        self._set_loading(self._login_inflight)
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

    def _restore_remembered_identity(self) -> None:
        try:
            remembered = session.get_remember_me() or {}
        except Exception:
            remembered = {}

        momo_number = str(remembered.get("momo") or "").strip()
        if not momo_number:
            return

        self.remember_me = True
        self._set_text(momo_number, "momo_input")

    def _sync_auth_controls(self) -> None:
        password_toggle = self.ids.get("password_toggle")
        if password_toggle is not None:
            if hasattr(password_toggle, "visible"):
                password_toggle.visible = self.password_visible
            elif hasattr(password_toggle, "icon"):
                password_toggle.icon = "eye" if self.password_visible else "eye-off"

        password_field = self.ids.get("pin_input")
        if password_field is not None:
            if hasattr(password_field, "password_visible"):
                password_field.password_visible = self.password_visible
            if hasattr(password_field, "password"):
                password_field.password = not self.password_visible

        remember_toggle = self.ids.get("remember_toggle")
        if remember_toggle is None:
            remember_toggle = self.ids.get("remember_me_toggle")
        if remember_toggle is not None:
            if hasattr(remember_toggle, "checked"):
                remember_toggle.checked = self.remember_me
            elif hasattr(remember_toggle, "active"):
                remember_toggle.active = self.remember_me

    def toggle_password(self):
        self.password_visible = not self.password_visible
        pin_field = self.ids.get("pin_input")
        if pin_field is not None:
            if hasattr(pin_field, "password_visible"):
                pin_field.password_visible = self.password_visible
            pin_field.password = not self.password_visible
        self._sync_auth_controls()

    def on_momo_input(self, text: str) -> None:
        if self._syncing_momo_input:
            return

        raw = str(text or "").strip()
        field = self.ids.get("momo_input")
        normalized = normalize_ghana_number(raw)
        if field is not None and normalized and normalized != raw:
            try:
                self._syncing_momo_input = True
                field.text = normalized
            finally:
                self._syncing_momo_input = False
            raw = normalized

        if len(normalized) != 10 or not normalized.startswith("0"):
            if self._lookup_event is not None:
                self._lookup_event.cancel()
                self._lookup_event = None
            self._lookup_seq = int(getattr(self, "_lookup_seq", 0)) + 1
            self.detected_first_name = ""
            self.network_text = (
                "Network: Enter your Ghana MoMo number to detect your network."
                if not raw
                else "Network: Enter a valid 10-digit Ghana MoMo number."
            )
            if not raw:
                self.name_hint_text = (
                    "We will confirm your saved profile name automatically if this number is already registered."
                )
            return

        network = detect_network(normalized)
        network_name = network.title() if network and network != "UNKNOWN" else "Unknown"
        self.network_text = f"Network: {network_name}"
        self.name_hint_text = "Checking for a saved profile name..."
        if self._lookup_event is not None:
            self._lookup_event.cancel()

        self._lookup_seq = int(getattr(self, "_lookup_seq", 0)) + 1
        seq = self._lookup_seq
        self._lookup_event = Clock.schedule_once(
            lambda _dt: Thread(
                target=self._lookup_name_worker,
                args=(seq, normalized),
                daemon=True,
            ).start(),
            0.6,
        )

    def _lookup_name_worker(self, seq: int, momo_number: str) -> None:
        try:
            response = lookup_registered_name(momo_number)
        except Exception:
            response = None
        Clock.schedule_once(
            lambda _dt: self._apply_lookup_response(seq, response)
        )

    def _apply_lookup_response(self, seq: int, response) -> None:
        if seq != int(getattr(self, "_lookup_seq", 0)):
            return
        first_name_field = self.ids.get("first_name_input")
        if first_name_field is None:
            return
        if not isinstance(response, dict):
            self.name_hint_text = (
                "We could not confirm the saved profile name right now. You can still continue."
            )
            return

        first_name = str(response.get("first_name") or "").strip()
        if response.get("registered") and first_name:
            self.detected_first_name = first_name
            first_name_field.text = first_name
            self.name_hint_text = f"Saved profile name: {first_name}"
            return

        self.detected_first_name = ""
        first_name_field.text = ""
        self.name_hint_text = "No saved profile name was found for this number."

    def submit(self):
        self.login()

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
        if self._login_inflight:
            return

        momo_number = self._get_text("momo_input")
        pin = self._get_text("pin_input")

        if momo_number == "":
            self.show_message("Please enter your MoMo number.")
            return

        if pin == "":
            self.show_message("Please enter your PIN.")
            return

        self._set_loading(True)
        self._login_inflight = True
        generation = self._login_generation
        Thread(
            target=self._login_worker,
            args=(momo_number, pin, generation),
            daemon=True,
        ).start()

    def _set_loading(self, value: bool) -> None:
        self.loading = bool(value)
        button = self.ids.get("login_button")
        if button is not None:
            if hasattr(button, "loading"):
                button.loading = bool(value)
            else:
                button.disabled = bool(value)

    def _login_worker(self, momo_number: str, pin: str, generation: int) -> None:
        try:
            result = self.controller.login(momo_number, pin, defer_apply=True)
        except Exception as exc:
            message = extract_backend_message(
                exc,
                fallback="Login failed. Please try again.",
            )
            Clock.schedule_once(lambda _dt, msg=message, gen=generation: self._finish_login_failure(msg, gen))
            return

        Clock.schedule_once(
            lambda _dt, res=result, momo=momo_number, gen=generation: self._apply_login_response(
                momo,
                res,
                gen,
            )
        )

    def _finish_login_failure(self, message: str, generation: int | None = None) -> None:
        self._login_inflight = False
        if not self._active or generation != self._login_generation:
            return
        self._set_loading(False)
        self.show_message(message)

    def _apply_login_response(self, momo_number: str, result: dict, generation: int | None = None) -> None:
        self._login_inflight = False
        if not self._active or generation != self._login_generation:
            return
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
                self.controller.apply_login_result(result, momo_number=momo_number, prepared=True)
                if self.remember_me:
                    self._save_remember_me(momo_number, result)
                else:
                    try:
                        session.clear_remember_me()
                    except Exception:
                        pass
                self.show_message("Login successful.")
                app = MDApp.get_running_app()
                target_screen = "home"
                if app is not None:
                    get_target = getattr(app, "get_authenticated_target", None)
                    if callable(get_target):
                        target_screen = str(get_target() or "home")
                    elif bool(getattr(app, "is_admin", False)):
                        target_screen = "admin_dashboard"
                    elif bool(getattr(app, "is_agent_active", False)):
                        target_screen = "agent_dashboard"
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
            return navigate(self.manager, screen_name, fallback=fallback, transition_style="fade")

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
        self.show_message("Google sign-in is not available yet.")

    def facebook_login(self):
        self.show_message("Facebook sign-in is not available yet.")

    def apple_login(self):
        self.show_message("Apple sign-in is not available yet.")

    def phone_login(self):
        momo_number = self._get_text("momo_input")
        pin = self._get_text("pin_input")

        if momo_number and pin:
            self.login()
            return

        target_id = "momo_input" if not momo_number else "pin_input"
        target = self.ids.get(target_id)
        if target is not None and hasattr(target, "focus"):
            target.focus = True

        self.show_message("Use your MoMo number and PIN.")

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
