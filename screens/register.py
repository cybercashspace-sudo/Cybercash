import re
import threading
from pathlib import Path

from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import BooleanProperty, ColorProperty, StringProperty
from kivymd.app import MDApp
from kivymd.uix.fitimage import FitImage

from api.auth import lookup_registered_name, register
from core.auth_assets import auth_asset_path
from core.message_sanitizer import extract_backend_message
from core.popup_manager import show_message_dialog
from core.responsive_screen import ResponsiveScreen
from utils.network import detect_network, normalize_ghana_number

DEFAULT_NETWORK_TEXT = "Network: Enter your Ghana MoMo number to detect your network."
DEFAULT_NAME_HINT_TEXT = "We will check whether this number already has a saved profile name."
DEFAULT_FEEDBACK_TEXT = "Create your wallet with your MoMo number, email, first name, and a secure 4-digit PIN."

KV = """
#:import dp kivy.metrics.dp
#:import sp kivy.metrics.sp
#:set BG (0.02, 0.02, 0.03, 1)
#:set BG_SOFT (0.08, 0.06, 0.02, 0.92)
#:set SURFACE (0.07, 0.07, 0.08, 0.96)
#:set SURFACE_SOFT (0.11, 0.12, 0.14, 0.96)
#:set GOLD (0.95, 0.79, 0.27, 1)
#:set GOLD_SOFT (0.98, 0.80, 0.22, 1)
#:set TEXT_MAIN (0.95, 0.95, 0.96, 1)
#:set TEXT_SUB (0.75, 0.77, 0.80, 1)
<RegisterScreen>:
    MDBoxLayout:
        orientation: "vertical"
        canvas.before:
            Color:
                rgba: BG
            Rectangle:
                pos: self.pos
                size: self.size
            Color:
                rgba: 0.24, 0.17, 0.03, 0.22
            Ellipse:
                pos: self.width - dp(310), self.height - dp(260)
                size: dp(420), dp(420)
            Color:
                rgba: BG_SOFT
            RoundedRectangle:
                pos: self.x - dp(18), self.y + dp(18)
                size: self.width + dp(36), self.height * 0.58
                radius: [dp(38), dp(38), dp(18), dp(18)]

        ScrollView:
            do_scroll_x: False
            bar_width: 0

            MDBoxLayout:
                orientation: "vertical"
                size_hint_y: None
                height: self.minimum_height
                padding: [dp(16 * root.layout_scale), dp(14 * root.layout_scale), dp(16 * root.layout_scale), dp(22 * root.layout_scale)]
                spacing: dp(12 * root.layout_scale)

                MDBoxLayout:
                    orientation: "vertical"
                    size_hint_y: None
                    height: self.minimum_height
                    spacing: dp(8 * root.layout_scale)

                    FitImage:
                        source: root.hero_source
                        size_hint_x: 1
                        size_hint_y: None
                        height: dp(232 * root.layout_scale)
                        pos_hint: {"center_x": 0.5}

                    MDLabel:
                        text: "YOUR MONEY. YOUR GOAL. YOUR WORLD."
                        halign: "center"
                        theme_text_color: "Custom"
                        text_color: TEXT_MAIN
                        font_size: sp(13.5 * root.text_scale)
                        bold: True
                        size_hint_y: None
                        height: self.texture_size[1] if self.text else 0

                MDCard:
                    radius: [dp(28 * root.layout_scale)]
                    padding: [dp(14 * root.layout_scale)] * 4
                    size_hint_y: None
                    height: self.minimum_height
                    md_bg_color: SURFACE
                    line_color: [0.92, 0.73, 0.22, 0.60]
                    elevation: 0

                    MDBoxLayout:
                        orientation: "vertical"
                        adaptive_height: True
                        spacing: dp(11 * root.layout_scale)

                        MDBoxLayout:
                            orientation: "horizontal"
                            spacing: dp(12 * root.layout_scale)
                            size_hint_y: None
                            height: dp(170 * root.layout_scale) if not root.compact_mode else dp(118 * root.layout_scale)

                            MDBoxLayout:
                                orientation: "vertical"
                                spacing: dp(8 * root.layout_scale)
                                size_hint_x: 0.56 if not root.compact_mode else 1
                                size_hint_y: 1

                                MDLabel:
                                    text: "Create Account"
                                    theme_text_color: "Custom"
                                    text_color: TEXT_MAIN
                                    bold: True
                                    font_size: sp(25 * root.text_scale)
                                    text_size: self.width, None
                                    halign: "left"
                                    size_hint_y: None
                                    height: self.texture_size[1] if self.text else 0

                                MDLabel:
                                    text: "Open your wallet in minutes"
                                    theme_text_color: "Custom"
                                    text_color: TEXT_SUB
                                    font_size: sp(13.5 * root.text_scale)
                                    text_size: self.width, None
                                    halign: "left"
                                    size_hint_y: None
                                    height: self.texture_size[1] if self.text else 0

                                MDBoxLayout:
                                    size_hint_y: None
                                    height: dp(34 * root.layout_scale)
                                    spacing: dp(18 * root.layout_scale)

                                    MDTextButton:
                                        text: "Login"
                                        theme_text_color: "Custom"
                                        text_color: TEXT_SUB
                                        font_size: sp(15 * root.text_scale)
                                        on_release: app.go_to_screen("login")

                                    MDBoxLayout:
                                        orientation: "vertical"
                                        size_hint_x: None
                                        width: self.minimum_width
                                        spacing: dp(4 * root.layout_scale)

                                        MDLabel:
                                            text: "Sign Up"
                                            theme_text_color: "Custom"
                                            text_color: GOLD
                                            bold: True
                                            font_size: sp(17 * root.text_scale)
                                            size_hint_y: None
                                            height: self.texture_size[1] if self.text else 0

                                        MDBoxLayout:
                                            size_hint_y: None
                                            height: dp(2 * root.layout_scale)
                                            canvas.before:
                                                Color:
                                                    rgba: GOLD
                                                Rectangle:
                                                    pos: self.pos
                                                    size: self.size

                            MDCard:
                                radius: [dp(20 * root.layout_scale)]
                                md_bg_color: SURFACE_SOFT
                                line_color: [0.90, 0.71, 0.16, 0.42]
                                elevation: 0
                                padding: dp(10 * root.layout_scale)
                                size_hint_x: 0.44 if not root.compact_mode else 0
                                size_hint_y: 1
                                opacity: 1 if not root.compact_mode else 0
                                disabled: root.compact_mode

                                FloatLayout:
                                    FitImage:
                                        source: root.card_art_source
                                        size_hint: 0.98, 0.98
                                        pos_hint: {"center_x": 0.5, "center_y": 0.52}

                                    MDIconButton:
                                        icon: "lock-outline"
                                        theme_text_color: "Custom"
                                        text_color: GOLD
                                        user_font_size: str(23 * root.icon_scale) + "sp"
                                        size_hint: None, None
                                        size: dp(34 * root.layout_scale), dp(34 * root.layout_scale)
                                        pos_hint: {"right": 0.98, "top": 0.98}
                                        disabled: True

                                    MDIconButton:
                                        icon: "shield-check-outline"
                                        theme_text_color: "Custom"
                                        text_color: GOLD
                                        user_font_size: str(22 * root.icon_scale) + "sp"
                                        size_hint: None, None
                                        size: dp(34 * root.layout_scale), dp(34 * root.layout_scale)
                                        pos_hint: {"right": 0.98, "y": 0.04}
                                        disabled: True

                                    MDCard:
                                        size_hint: None, None
                                        size: dp(154 * root.layout_scale), dp(82 * root.layout_scale)
                                        radius: [dp(16 * root.layout_scale)]
                                        md_bg_color: [0.05, 0.05, 0.06, 0.96]
                                        line_color: [0.93, 0.75, 0.20, 0.55]
                                        elevation: 0
                                        padding: [dp(10 * root.layout_scale)] * 4
                                        pos_hint: {"right": 0.98, "y": 0.04}

                                        MDBoxLayout:
                                            orientation: "vertical"
                                            spacing: dp(1 * root.layout_scale)

                                            MDLabel:
                                                text: "CYBER CASH"
                                                theme_text_color: "Custom"
                                                text_color: GOLD
                                                bold: True
                                                font_size: sp(8.8 * root.text_scale)
                                                size_hint_y: None
                                                height: self.texture_size[1] if self.text else 0

                                            MDLabel:
                                                text: "1234 5678 9012 3456"
                                                theme_text_color: "Custom"
                                                text_color: TEXT_MAIN
                                                font_size: sp(7.6 * root.text_scale)
                                                size_hint_y: None
                                                height: self.texture_size[1] if self.text else 0

                                            MDLabel:
                                                text: "VISA"
                                                halign: "right"
                                                theme_text_color: "Custom"
                                                text_color: TEXT_MAIN
                                                bold: True
                                                font_size: sp(10 * root.text_scale)
                                                size_hint_y: None
                                                height: self.texture_size[1] if self.text else 0

                        MDBoxLayout:
                            size_hint_y: None
                            height: dp(1 * root.layout_scale)
                            canvas.before:
                                Color:
                                    rgba: 0.90, 0.72, 0.18, 0.34
                                Rectangle:
                                    pos: self.pos
                                    size: self.size

                        MDBoxLayout:
                            orientation: "horizontal"
                            adaptive_height: True
                            spacing: dp(10 * root.layout_scale)

                            MDIconButton:
                                icon: "phone-outline"
                                theme_text_color: "Custom"
                                text_color: GOLD
                                user_font_size: str(22 * root.icon_scale) + "sp"
                                size_hint: None, None
                                size: dp(36 * root.layout_scale), dp(36 * root.layout_scale)
                                disabled: True

                            MDTextField:
                                id: momo_input
                                hint_text: "MoMo number"
                                helper_text: root.network_text
                                helper_text_mode: "on_focus"
                                mode: "fill"
                                theme_bg_color: "Custom"
                                fill_color_normal: 0.11, 0.12, 0.14, 1
                                fill_color_focus: 0.14, 0.15, 0.18, 1
                                theme_line_color: "Custom"
                                line_color_normal: 0.28, 0.22, 0.08, 0.76
                                line_color_focus: GOLD
                                text_color_normal: TEXT_MAIN
                                text_color_focus: TEXT_MAIN
                                font_size: sp(13.5 * root.text_scale)
                                multiline: False
                                on_text: root.on_momo_input(self.text)

                        MDLabel:
                            text: root.name_hint_text if root.detected_first_name else ""
                            theme_text_color: "Custom"
                            text_color: GOLD
                            font_size: sp(11.5 * root.text_scale)
                            text_size: self.width, None
                            halign: "left"
                            size_hint_y: None
                            height: self.texture_size[1] if self.text else 0
                            opacity: 1 if root.detected_first_name else 0

                        MDBoxLayout:
                            orientation: "horizontal"
                            adaptive_height: True
                            spacing: dp(10 * root.layout_scale)

                            MDIconButton:
                                icon: "email-outline"
                                theme_text_color: "Custom"
                                text_color: GOLD
                                user_font_size: str(22 * root.icon_scale) + "sp"
                                size_hint: None, None
                                size: dp(36 * root.layout_scale), dp(36 * root.layout_scale)
                                disabled: True

                            MDTextField:
                                id: email_input
                                hint_text: "Email address"
                                helper_text: "This email receives receipts and verification updates."
                                helper_text_mode: "on_focus"
                                mode: "fill"
                                theme_bg_color: "Custom"
                                fill_color_normal: 0.11, 0.12, 0.14, 1
                                fill_color_focus: 0.14, 0.15, 0.18, 1
                                theme_line_color: "Custom"
                                line_color_normal: 0.28, 0.22, 0.08, 0.76
                                line_color_focus: GOLD
                                text_color_normal: TEXT_MAIN
                                text_color_focus: TEXT_MAIN
                                font_size: sp(13.5 * root.text_scale)
                                multiline: False

                        MDBoxLayout:
                            orientation: "horizontal"
                            adaptive_height: True
                            spacing: dp(10 * root.layout_scale)

                            MDIconButton:
                                icon: "account-outline"
                                theme_text_color: "Custom"
                                text_color: GOLD
                                user_font_size: str(22 * root.icon_scale) + "sp"
                                size_hint: None, None
                                size: dp(36 * root.layout_scale), dp(36 * root.layout_scale)
                                disabled: True

                            MDTextField:
                                id: first_name_input
                                hint_text: "First name"
                                helper_text: "We use this for your profile name."
                                helper_text_mode: "on_focus"
                                mode: "fill"
                                theme_bg_color: "Custom"
                                fill_color_normal: 0.11, 0.12, 0.14, 1
                                fill_color_focus: 0.14, 0.15, 0.18, 1
                                theme_line_color: "Custom"
                                line_color_normal: 0.28, 0.22, 0.08, 0.76
                                line_color_focus: GOLD
                                text_color_normal: TEXT_MAIN
                                text_color_focus: TEXT_MAIN
                                font_size: sp(13.5 * root.text_scale)
                                multiline: False

                        MDBoxLayout:
                            orientation: "horizontal"
                            adaptive_height: True
                            spacing: dp(10 * root.layout_scale)

                            MDIconButton:
                                icon: "shield-lock-outline"
                                theme_text_color: "Custom"
                                text_color: GOLD
                                user_font_size: str(22 * root.icon_scale) + "sp"
                                size_hint: None, None
                                size: dp(36 * root.layout_scale), dp(36 * root.layout_scale)
                                disabled: True

                            MDTextField:
                                id: pin_input
                                hint_text: "PIN"
                                helper_text: "Create a secure 4-digit PIN."
                                helper_text_mode: "on_focus"
                                mode: "fill"
                                theme_bg_color: "Custom"
                                fill_color_normal: 0.11, 0.12, 0.14, 1
                                fill_color_focus: 0.14, 0.15, 0.18, 1
                                theme_line_color: "Custom"
                                line_color_normal: 0.28, 0.22, 0.08, 0.76
                                line_color_focus: GOLD
                                text_color_normal: TEXT_MAIN
                                text_color_focus: TEXT_MAIN
                                font_size: sp(13.5 * root.text_scale)
                                password: not root.pin_visible
                                max_text_length: 4
                                multiline: False

                            MDIconButton:
                                icon: "eye" if root.pin_visible else "eye-off"
                                theme_text_color: "Custom"
                                text_color: GOLD
                                user_font_size: str(22 * root.icon_scale) + "sp"
                                size_hint: None, None
                                size: dp(36 * root.layout_scale), dp(36 * root.layout_scale)
                                on_release: root.toggle_pin_visibility()

                        MDBoxLayout:
                            adaptive_height: True
                            spacing: dp(8 * root.layout_scale)

                            MDCheckbox:
                                id: agent_checkbox
                                active: False
                                disabled: True
                                opacity: 0
                                size_hint: None, None
                                size: dp(0), dp(0)

                            MDLabel:
                                text: "Verification will finish setup after the OTP step."
                                valign: "center"
                                theme_text_color: "Custom"
                                text_color: TEXT_MAIN
                                font_size: sp(12.2 * root.text_scale)

                        MDLabel:
                            text: root.feedback_text
                            theme_text_color: "Custom"
                            text_color: root.feedback_color
                            font_size: sp(12 * root.text_scale)
                            text_size: self.width, None
                            halign: "left"
                            size_hint_y: None
                            height: self.texture_size[1] if self.text else 0

                        MDFillRoundFlatIconButton:
                            text: "Create Account"
                            icon: "account-check-outline"
                            md_bg_color: GOLD_SOFT
                            text_color: BG
                            size_hint_y: None
                            height: dp(58 * root.layout_scale)
                            on_release: root.register_account()

                        MDTextButton:
                            text: "Back to Login"
                            theme_text_color: "Custom"
                            text_color: GOLD
                            pos_hint: {"center_x": 0.5}
                            font_size: sp(12.5 * root.text_scale)
                            on_release: app.go_to_screen("login")
"""


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
        except Exception as exc:
            response = {"detail": str(exc) or "Registration failed."}
        Clock.schedule_once(lambda _dt: self._apply_register_response(momo, first_name, response))

    def _apply_register_response(self, momo: str, first_name: str, response: dict):
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
            app.pending_momo = momo
            self._set_feedback("OTP sent to your email. Verify your account to continue.", "success")
            if self.manager and self.manager.has_screen("otp"):
                otp_screen = self.manager.get_screen("otp")
                otp_screen.momo_number = momo
                self._show_popup(
                    "Registration Successful",
                    "Your account is ready. Tap Close to continue with email verification.",
                    on_close=lambda: setattr(self.manager, "current", "otp") if self.manager else None,
                )
            elif self.manager:
                self._show_popup(
                    "Registration Successful",
                    "Your account is ready. Please sign in to continue and verify by email.",
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
