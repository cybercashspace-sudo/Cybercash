import threading

from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import ColorProperty, StringProperty
from kivymd.app import MDApp

from api.auth import access_account, lookup_registered_name
from core.message_sanitizer import extract_backend_message
from core.popup_manager import show_message_dialog
from core.responsive_screen import ResponsiveScreen
from storage import save_token
from utils.network import detect_network, normalize_ghana_number

DEFAULT_NETWORK_TEXT = "Network: Enter your Ghana MoMo number to detect your network."
DEFAULT_NAME_HINT_TEXT = "We will confirm your saved profile name automatically if this number is already registered."
DEFAULT_FEEDBACK_TEXT = "Welcome back. Enter your MoMo number and 4-digit PIN to sign in securely."

KV = """
#:import dp kivy.metrics.dp
#:import sp kivy.metrics.sp
#:set BG (0.03, 0.04, 0.06, 1)
#:set BG_SOFT (0.07, 0.08, 0.11, 0.88)
#:set SURFACE (0.08, 0.10, 0.14, 0.95)
#:set SURFACE_SOFT (0.12, 0.14, 0.18, 0.95)
#:set GOLD (0.94, 0.79, 0.46, 1)
#:set GOLD_SOFT (0.93, 0.77, 0.39, 1)
#:set TEXT_MAIN (0.95, 0.95, 0.95, 1)
#:set TEXT_SUB (0.74, 0.76, 0.80, 1)
<LoginScreen>:
    MDBoxLayout:
        orientation: "vertical"
        canvas.before:
            Color:
                rgba: BG
            Rectangle:
                pos: self.pos
                size: self.size
            Color:
                rgba: BG_SOFT
            RoundedRectangle:
                pos: self.x - dp(20), self.y + dp(36)
                size: self.width + dp(40), self.height * 0.62
                radius: [dp(42), dp(42), dp(16), dp(16)]

        ScrollView:
            do_scroll_x: False
            bar_width: 0

            MDBoxLayout:
                orientation: "vertical"
                size_hint_y: None
                height: self.minimum_height
                padding: [dp(16 * root.layout_scale), dp(16 * root.layout_scale), dp(16 * root.layout_scale), dp(20 * root.layout_scale)]
                spacing: dp(11 * root.layout_scale)

                MDCard:
                    radius: [dp(24 * root.layout_scale)]
                    padding: [dp(15 * root.layout_scale)] * 4
                    size_hint_y: None
                    height: dp(126 * root.layout_scale)
                    md_bg_color: SURFACE
                    elevation: 0

                    MDBoxLayout:
                        orientation: "vertical"
                        spacing: dp(6 * root.layout_scale)

                        MDBoxLayout:
                            adaptive_height: True
                            spacing: dp(8 * root.layout_scale)

                            MDIconButton:
                                icon: "account-circle"
                                user_font_size: str(42 * root.icon_scale) + "sp"
                                theme_text_color: "Custom"
                                text_color: GOLD
                                disabled: True

                            MDLabel:
                                text: "CYBER CASH"
                                font_style: "Title"
                                font_size: sp(24 * root.text_scale)
                                bold: True
                                theme_text_color: "Custom"
                                text_color: GOLD

                        MDBoxLayout:
                            size_hint_y: None
                            height: "1dp"
                            canvas.before:
                                Color:
                                    rgba: 0.94, 0.79, 0.46, 0.28
                                Rectangle:
                                    pos: self.pos
                                    size: self.size

                        MDLabel:
                            text: "Sign in to your wallet, transfers, cards, and agent tools."
                            theme_text_color: "Custom"
                            text_color: TEXT_MAIN

                MDCard:
                    radius: [dp(22 * root.layout_scale)]
                    padding: [dp(15 * root.layout_scale)] * 4
                    md_bg_color: SURFACE_SOFT
                    elevation: 0
                    adaptive_height: True

                    MDBoxLayout:
                        orientation: "vertical"
                        adaptive_height: True
                        spacing: dp(10 * root.layout_scale)

                        MDTextField:
                            id: momo_input
                            hint_text: "MoMo number"
                            mode: "outlined"
                            icon_right: "phone"
                            line_color_focus: GOLD
                            on_text: root.on_momo_input(self.text)

                        MDLabel:
                            text: "Use your 10-digit registered Ghana MoMo number, for example 0241234567."
                            theme_text_color: "Custom"
                            text_color: TEXT_SUB
                            font_size: sp(11.5 * root.text_scale)
                            adaptive_height: True

                        MDTextField:
                            id: first_name_input
                            hint_text: "First name"
                            mode: "outlined"
                            icon_right: "account-outline"
                            line_color_focus: GOLD

                        MDLabel:
                            text: "We auto-fill this when we find your saved profile name for the number above."
                            theme_text_color: "Custom"
                            text_color: TEXT_SUB
                            font_size: sp(11.5 * root.text_scale)
                            adaptive_height: True

                        MDTextField:
                            id: pin_input
                            hint_text: "4-digit PIN"
                            mode: "outlined"
                            icon_right: "shield-lock-outline"
                            line_color_focus: GOLD
                            password: True
                            max_text_length: 4

                        MDLabel:
                            text: "Enter the same 4-digit PIN linked to this wallet."
                            theme_text_color: "Custom"
                            text_color: TEXT_SUB
                            font_size: sp(11.5 * root.text_scale)
                            adaptive_height: True

                        MDBoxLayout:
                            adaptive_height: True
                            spacing: "8dp"

                            MDCheckbox:
                                id: agent_toggle
                                size_hint: None, None
                                size: dp(34 * root.layout_scale), dp(34 * root.layout_scale)

                            MDLabel:
                                text: "Turn this on only when opening an agent account for the first time."
                                valign: "middle"
                                theme_text_color: "Custom"
                                text_color: TEXT_MAIN

                        MDLabel:
                            text: root.network_text
                            theme_text_color: "Custom"
                            text_color: TEXT_SUB
                            adaptive_height: True

                        MDLabel:
                            text: root.name_hint_text
                            theme_text_color: "Custom"
                            text_color: GOLD
                            adaptive_height: True

                        MDLabel:
                            text: root.feedback_text
                            theme_text_color: "Custom"
                            text_color: root.feedback_color
                            adaptive_height: True

                        MDFillRoundFlatIconButton:
                            text: "Sign In"
                            icon: "login-variant"
                            md_bg_color: GOLD_SOFT
                            text_color: BG
                            size_hint_y: None
                            height: dp(56 * root.layout_scale)
                            on_release: root.submit()

                        MDTextButton:
                            text: "Create New Account"
                            theme_text_color: "Custom"
                            text_color: GOLD
                            pos_hint: {"center_x": 0.5}
                            on_release:
                                if root.manager: root.manager.current = "register"
"""


class LoginScreen(ResponsiveScreen):
    network_text = StringProperty(DEFAULT_NETWORK_TEXT)
    name_hint_text = StringProperty(DEFAULT_NAME_HINT_TEXT)
    feedback_text = StringProperty(DEFAULT_FEEDBACK_TEXT)
    feedback_color = ColorProperty([0.72, 0.74, 0.79, 1])
    detected_first_name = StringProperty("")

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

    def on_momo_input(self, text: str):
        network = detect_network(text)
        normalized = normalize_ghana_number(text)
        if not normalized or len(normalized) != 10 or not normalized.startswith("0"):
            self.network_text = DEFAULT_NETWORK_TEXT
            self.name_hint_text = DEFAULT_NAME_HINT_TEXT
            self.detected_first_name = ""
            return
        display_name = network.title() if network != "UNKNOWN" else "Unknown"
        self.network_text = f"Network: {display_name}"

        self._lookup_seq = int(getattr(self, "_lookup_seq", 0)) + 1
        seq = self._lookup_seq
        threading.Thread(target=self._lookup_name_worker, args=(seq, normalized), daemon=True).start()

    def _lookup_name_worker(self, seq: int, momo: str):
        response = lookup_registered_name(momo)
        Clock.schedule_once(lambda _dt: self._apply_lookup_response(seq, momo, response))

    def _apply_lookup_response(self, seq: int, momo: str, response: dict):
        if seq != int(getattr(self, "_lookup_seq", 0)):
            return
        if not isinstance(response, dict):
            self.name_hint_text = "We could not confirm the profile name right now. You can still continue."
            return

        registered = bool(response.get("registered"))
        first_name = str(response.get("first_name") or "").strip()
        network = str(response.get("network") or detect_network(momo)).strip()
        network_display = network.title() if network and network != "UNKNOWN" else "Unknown"

        if registered and first_name:
            self.detected_first_name = first_name
            if not self.ids.first_name_input.text.strip():
                self.ids.first_name_input.text = first_name
            self.name_hint_text = f"We found your saved profile name: {first_name}."
            return

        self.detected_first_name = ""
        if not self.ids.first_name_input.text.strip():
            self.ids.first_name_input.text = ""
        self.name_hint_text = (
            f"No saved profile name was found on {network_display}. "
            "If this is your first sign-in, enter your first name to continue."
        )

    def submit(self):
        app = MDApp.get_running_app()
        raw_momo = self.ids.momo_input.text.strip()
        momo = normalize_ghana_number(raw_momo)
        first_name = self.ids.first_name_input.text.strip() or self.detected_first_name.strip() or "Customer"
        pin = self.ids.pin_input.text.strip()
        is_agent = bool(self.ids.agent_toggle.active)

        if not momo or len(momo) != 10 or not momo.startswith("0"):
            self._set_feedback("Enter a valid 10-digit Ghana MoMo number.", "error")
            self._show_popup("Invalid Number", "Please enter a valid 10-digit Ghana MoMo number.")
            return

        if len(pin) != 4 or not pin.isdigit():
            self._set_feedback("PIN must be exactly 4 digits.", "error")
            self._show_popup("Invalid PIN", "PIN must be exactly 4 digits.")
            return

        self.ids.momo_input.text = momo
        self._set_feedback("Signing in...", "info")

        response = access_account(momo, pin, is_agent, first_name=first_name)
        status = str(response.get("status", "")).strip().lower() if isinstance(response, dict) else ""
        debug_otp = str(response.get("debug_otp", "") or "").strip() if isinstance(response, dict) else ""
        otp_hint = f"\n\nTest OTP: {debug_otp}" if debug_otp else ""

        if status == "login_success":
            token = str(response.get("access_token", "") or "")
            detected = str(response.get("first_name", "") or "").strip()
            app.access_token = token
            app.pending_momo = ""
            if detected:
                app.pending_momo = detected
            save_token(token)
            self._set_feedback("Login successful.", "success")
            welcome_name = detected or first_name or "User"
            self._show_popup(
                "Login Successful",
                f"Welcome back, {welcome_name}.",
                on_close=lambda: setattr(self.manager, "current", "home") if self.manager else None,
            )
            return

        if status in {"registered", "verify_required"}:
            detected = str(response.get("first_name", "") or "").strip()
            if detected:
                self.ids.first_name_input.text = detected
            app.pending_momo = momo
            self._set_feedback("Verification required. Enter the OTP sent to your phone.", "warning")
            if self.manager.has_screen("otp"):
                otp_screen = self.manager.get_screen("otp")
                otp_screen.momo_number = momo
                self._show_popup(
                    "Verification Required",
                    f"We sent an OTP to your number. Tap Close to continue verification.{otp_hint}",
                    on_close=lambda: setattr(self.manager, "current", "otp") if self.manager else None,
                )
            return

        if status == "pending_kyc":
            self._set_feedback("Agent onboarding is pending KYC approval.", "warning")
            self._show_popup(
                "KYC Pending",
                "Your agent onboarding is pending approval. You can sign in after KYC review is complete.",
            )
            return

        error_message = self._extract_detail(response) or "Unable to sign in right now."
        self._set_feedback(error_message, "error")
        self._show_popup("Sign-in Failed", error_message)


Builder.load_string(KV)
