import re
import threading
from pathlib import Path

from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import BooleanProperty, ColorProperty, StringProperty
from kivymd.app import MDApp

from api.auth import lookup_registered_name, register
from core.auth_assets import auth_asset_path
from core.message_sanitizer import extract_backend_message
from core.popup_manager import show_message_dialog
from core.responsive_screen import ResponsiveScreen
from utils.network import detect_network, normalize_ghana_number

DEFAULT_NETWORK_TEXT = "Network: Enter your Ghana MoMo number to detect your network."
DEFAULT_NAME_HINT_TEXT = "We will check whether this number already has a saved profile name."
DEFAULT_FEEDBACK_TEXT = "Create your wallet with your MoMo number, email for OTP and notifications, first name, and a secure 4-digit PIN."



class RegisterScreen(ResponsiveScreen):
    content_max_width = 430.0
    network_text = StringProperty(DEFAULT_NETWORK_TEXT)
    name_hint_text = StringProperty(DEFAULT_NAME_HINT_TEXT)
    feedback_text = StringProperty(DEFAULT_FEEDBACK_TEXT)
    feedback_color = ColorProperty([0.72, 0.74, 0.79, 1])
    detected_first_name = StringProperty("")
    hero_source = StringProperty("")
    card_art_source = StringProperty("")
    brand_tagline = StringProperty("YOUR MONEY. YOUR GOAL. YOUR WORLD.")
    pin_visible = BooleanProperty(False)
    agent_mode = BooleanProperty(False)
    _registering = False
    _syncing_momo_input = False
    _lookup_event = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.hero_source = auth_asset_path("00_full_reference.png")
        self.card_art_source = auth_asset_path("03_phone_card_lock_cluster.png")

    def on_pre_enter(self, *_args):
        self.agent_mode = False
        self.pin_visible = False
        agent_checkbox = self.ids.get("agent_checkbox")
        if agent_checkbox is not None:
            agent_checkbox.active = False
        pin_input = self.ids.get("pin_input")
        if pin_input is not None:
            if hasattr(pin_input, "password_visible"):
                pin_input.password_visible = False
            if hasattr(pin_input, "password"):
                pin_input.password = True

    def _set_feedback(self, message: str, level: str = "info"):
        palette = {
            "info": [0.72, 0.74, 0.79, 1],
            "success": [0.54, 0.82, 0.67, 1],
            "warning": [0.94, 0.80, 0.46, 1],
            "error": [0.96, 0.46, 0.41, 1],
        }
        self.feedback_text = str(message or "").strip()
        self.feedback_color = palette.get(level, palette["info"])

    def _show_popup(self, title: str, message: str, on_close=None):
        show_message_dialog(self, title=title, message=message, close_label="Close", on_close=on_close)

    @staticmethod
    def _extract_detail(response: dict) -> str:
        return extract_backend_message(response)

    def toggle_pin_visibility(self):
        self.pin_visible = not bool(self.pin_visible)
        pin_input = self.ids.get("pin_input")
        if pin_input is not None:
            if hasattr(pin_input, "password_visible"):
                pin_input.password_visible = self.pin_visible
            if hasattr(pin_input, "password"):
                pin_input.password = not self.pin_visible

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

    def on_momo_input(self, text: str):
        if self._syncing_momo_input:
            return
        field = self.ids.get("momo_input")
        if field is not None:
            normalized = normalize_ghana_number(text)
            if normalized and normalized != str(text or "").strip():
                try:
                    self._syncing_momo_input = True
                    field.text = normalized
                finally:
                    self._syncing_momo_input = False

        network = detect_network(text)
        normalized = normalize_ghana_number(text)
        if not normalized or len(normalized) != 10 or not normalized.startswith("0"):
            if self._lookup_event:
                self._lookup_event.cancel()
                self._lookup_event = None
            if not text.strip():
                self.network_text = DEFAULT_NETWORK_TEXT
                self.name_hint_text = DEFAULT_NAME_HINT_TEXT
            else:
                self.network_text = "Invalid number format..."
                self.name_hint_text = DEFAULT_NAME_HINT_TEXT
            self.detected_first_name = ""
            return
        display_name = "Unknown" if network == "UNKNOWN" else network.title()
        self.network_text = f"Network: {display_name}"

        if self._lookup_event:
            self._lookup_event.cancel()

        self._lookup_seq = int(getattr(self, "_lookup_seq", 0)) + 1
        seq = self._lookup_seq
        self._lookup_event = Clock.schedule_once(
            lambda dt: threading.Thread(
                target=self._lookup_name_worker, args=(seq, normalized), daemon=True
            ).start(),
            0.6,
        )

    def _lookup_name_worker(self, seq: int, momo: str):
        response = lookup_registered_name(momo)
        Clock.schedule_once(lambda _dt: self._apply_lookup_response(seq, momo, response))

    def _apply_lookup_response(self, seq: int, momo: str, response: dict):
        if seq != int(getattr(self, "_lookup_seq", 0)):
            return
        if not isinstance(response, dict):
            self.name_hint_text = "We could not confirm the saved profile name right now. You can still continue."
            return

        registered = bool(response.get("registered"))
        first_name = str(response.get("first_name") or "").strip()
        network = str(response.get("network") or detect_network(momo)).strip()
        network_display = network.title() if network and network != "UNKNOWN" else "Unknown"

        if registered and first_name:
            self.detected_first_name = first_name
            if not self.ids.first_name_input.text.strip():
                self.ids.first_name_input.text = first_name
            self.name_hint_text = f"We found an existing profile name: {first_name}. You can keep it or update it."
            return

        self.detected_first_name = ""
        if not self.ids.first_name_input.text.strip():
            self.ids.first_name_input.text = ""
        self.name_hint_text = (
            f"No saved profile name was found on {network_display}. "
            "Enter the first name you want to use for this wallet."
        )

    def register_account(self):
        if self._registering:
            return

        raw_momo = self.ids.momo_input.text.strip()
        momo = normalize_ghana_number(raw_momo)
        email = self.ids.email_input.text.strip().lower()
        first_name = self.ids.first_name_input.text.strip() or self.detected_first_name.strip() or "Customer"
        pin = self.ids.pin_input.text.strip()
        agent_mode = bool(self.agent_mode)

        if not momo or len(momo) != 10 or not momo.startswith("0"):
            self._set_feedback("Enter a valid 10-digit Ghana MoMo number.", "error")
            self._show_popup("Invalid Number", "Please enter a valid 10-digit Ghana MoMo number.")
            return

        if not email or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            self._set_feedback("Enter a valid email address.", "error")
            self._show_popup("Invalid Email", "Please enter a valid email address.")
            return

        if len(pin) != 4 or not pin.isdigit():
            self._set_feedback("PIN must be exactly 4 digits.", "error")
            self._show_popup("Invalid PIN", "PIN must be exactly 4 digits.")
            return

        self.ids.momo_input.text = momo
        self.ids.email_input.text = email
        self._set_feedback("Creating your agent account..." if agent_mode else "Creating your account...", "info")

        self._registering = True

        threading.Thread(
            target=self._register_account_worker,
            args=(momo, email, pin, agent_mode, first_name),
            daemon=True,
        ).start()

    def _register_account_worker(self, momo: str, email: str, pin: str, agent_mode: bool, first_name: str):
        try:
            response = register(momo, email, pin, agent_mode, first_name=first_name)
        except Exception:
            response = {"detail": "Registration failed. Please check your connection and try again."}
        Clock.schedule_once(lambda _dt: self._apply_register_response(momo, email, first_name, response))

    def _apply_register_response(self, momo: str, email: str, first_name: str, response: dict):
        self._registering = False
        app = MDApp.get_running_app()

        status = str(response.get("status", "")).strip().lower() if isinstance(response, dict) else ""

        if status in {"registered", "verify_required"} or (
            isinstance(response, dict) and response.get("message") and not response.get("detail")
        ):
            detected = str(response.get("first_name", "") or "").strip()
            display_name = detected or first_name or "Cyber Cash User"
            if detected:
                self.ids.first_name_input.text = detected
            app.user_name = display_name
            app.user_email = email
            app.pending_momo = momo
            self._set_feedback("OTP sent to your email. Verify your account to continue.", "success")
            if self.manager and self.manager.has_screen("otp"):
                otp_screen = self.manager.get_screen("otp")
                otp_screen.momo_number = momo
                self._show_popup(
                    "Registration Successful",
                    "Your account is ready. Check your email for the OTP to continue.",
                    on_close=lambda: setattr(self.manager, "current", "otp") if self.manager else None,
                )
            elif self.manager:
                self._show_popup(
                    "Registration Successful",
                    "Your account is ready. Please sign in and verify with the OTP sent to your email.",
                    on_close=lambda: setattr(self.manager, "current", "login") if self.manager else None,
                )
            return

        error_message = self._extract_detail(response) or "Registration failed."
        self._set_feedback(error_message, "error")
        self._show_popup("Registration Failed", error_message)


_REGISTER_KV = str(Path(__file__).with_name("register.kv"))
_LOADED_KV_FILES = list(getattr(Builder, "files", []) or [])
if _REGISTER_KV not in _LOADED_KV_FILES:
    Builder.load_file(_REGISTER_KV)
