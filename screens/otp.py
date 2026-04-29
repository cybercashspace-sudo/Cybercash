from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import BooleanProperty, ColorProperty, StringProperty
from kivymd.app import MDApp

from api.auth import resend_otp, verify_account
from core.message_sanitizer import extract_backend_message
from core.popup_manager import show_message_dialog
from core.responsive_screen import ResponsiveScreen
from storage import save_token
from utils.network import normalize_ghana_number

DEFAULT_OTP_FEEDBACK_TEXT = "Enter the 6-digit OTP we sent to your phone to complete secure access."

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
<OTPScreen>:
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
                                icon: "shield-check-outline"
                                user_font_size: str(40 * root.icon_scale) + "sp"
                                theme_text_color: "Custom"
                                text_color: GOLD
                                disabled: True

                            MDLabel:
                                text: "Verify Account"
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
                            text: "Enter the 6-digit code sent to your MoMo number to continue securely."
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

                        MDLabel:
                            text: "Use the same MoMo number you used during login or registration."
                            theme_text_color: "Custom"
                            text_color: TEXT_SUB
                            font_size: sp(11.5 * root.text_scale)
                            adaptive_height: True

                        MDTextField:
                            id: otp_input
                            hint_text: "6-digit OTP"
                            mode: "outlined"
                            icon_right: "shield-key-outline"
                            line_color_focus: GOLD
                            max_text_length: 6

                        MDLabel:
                            text: "Enter the 6-digit code from SMS exactly as received."
                            theme_text_color: "Custom"
                            text_color: TEXT_SUB
                            font_size: sp(11.5 * root.text_scale)
                            adaptive_height: True

                        MDLabel:
                            text: root.feedback_text
                            theme_text_color: "Custom"
                            text_color: root.feedback_color
                            adaptive_height: True

                        MDFillRoundFlatIconButton:
                            text: "Verify OTP"
                            icon: "check-circle-outline"
                            md_bg_color: GOLD_SOFT
                            text_color: BG
                            size_hint_y: None
                            height: dp(56 * root.layout_scale)
                            on_release: root.verify()

                        MDTextButton:
                            text: root.timer_text
                            disabled: not root.can_resend
                            theme_text_color: "Custom"
                            text_color: GOLD
                            pos_hint: {"center_x": 0.5}
                            on_release: root.resend()

                        MDTextButton:
                            text: "Back to Login"
                            theme_text_color: "Custom"
                            text_color: GOLD
                            pos_hint: {"center_x": 0.5}
                            on_release:
                                if root.manager: root.manager.current = "login"
"""


class OTPScreen(ResponsiveScreen):
    momo_number = None
    countdown = 120
    timer_event = None

    timer_text = StringProperty("You can request a new OTP in 120s")
    can_resend = BooleanProperty(False)
    feedback_text = StringProperty(DEFAULT_OTP_FEEDBACK_TEXT)
    feedback_color = ColorProperty([0.72, 0.74, 0.79, 1])

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

    def on_enter(self):
        if self.momo_number:
            self.ids.momo_input.text = self.momo_number
            self._set_feedback(
                f"We sent a 6-digit OTP to {self.momo_number}. Enter it below to continue.",
                "info",
            )
        else:
            self._set_feedback(DEFAULT_OTP_FEEDBACK_TEXT, "info")
        self.start_timer()

    def on_leave(self):
        if self.timer_event:
            self.timer_event.cancel()
            self.timer_event = None

    def start_timer(self):
        self.countdown = 120
        self.can_resend = False
        self.timer_text = f"You can request a new OTP in {self.countdown}s"
        if self.timer_event:
            self.timer_event.cancel()
        self.timer_event = Clock.schedule_interval(self.update_timer, 1)

    def update_timer(self, _dt):
        self.countdown -= 1
        if self.countdown <= 0:
            if self.timer_event:
                self.timer_event.cancel()
                self.timer_event = None
            self.timer_text = "Resend OTP now"
            self.can_resend = True
            return False

        self.timer_text = f"You can request a new OTP in {self.countdown}s"
        return True

    def verify(self):
        app = MDApp.get_running_app()
        momo = normalize_ghana_number((self.ids.momo_input.text or self.momo_number or "").strip())
        otp = self.ids.otp_input.text.strip()

        if not momo or len(momo) != 10 or not momo.startswith("0"):
            self._set_feedback("Enter the same valid 10-digit Ghana MoMo number used earlier.", "error")
            self._show_popup("Invalid Number", "Please enter the same valid 10-digit Ghana MoMo number used earlier.")
            return

        if len(otp) != 6 or not otp.isdigit():
            self._set_feedback("OTP must be exactly 6 digits.", "error")
            self._show_popup("Invalid OTP", "OTP must be exactly 6 digits.")
            return

        self._set_feedback("Verifying OTP...", "info")
        response = verify_account(momo, otp)

        if str(response.get("status", "")).strip().lower() == "verified":
            token = str(response.get("access_token", "") or "")
            first_name = str(response.get("first_name", "") or "").strip()
            save_token(token)
            app.access_token = token
            app.pending_momo = first_name or ""
            self._set_feedback("Verification successful.", "success")
            self._show_popup(
                "Verification Successful",
                "Your account is verified and ready to use.",
                on_close=lambda: setattr(self.manager, "current", "home") if self.manager else None,
            )
            return

        error_message = self._extract_detail(response) or "Verification failed."
        self._set_feedback(error_message, "error")
        self._show_popup("Verification Failed", error_message)

    def resend(self):
        momo = normalize_ghana_number((self.ids.momo_input.text or self.momo_number or "").strip())
        if not self.can_resend:
            self._show_popup("Please Wait", "Please wait for the timer to finish before requesting another OTP.")
            return
        if not momo or len(momo) != 10 or not momo.startswith("0"):
            self._set_feedback("Enter a valid MoMo number to resend OTP.", "error")
            self._show_popup("Invalid Number", "Please enter a valid MoMo number to resend OTP.")
            return

        response = resend_otp(momo)
        if not isinstance(response, dict) or response.get("detail"):
            error_message = self._extract_detail(response) or "Unable to resend OTP right now."
            self._set_feedback(error_message, "error")
            self._show_popup("Resend Failed", error_message)
            return

        info_message = self._extract_detail(response) or "A new OTP has been sent to your MoMo number."
        debug_otp = str(response.get("debug_otp", "") or "").strip()
        if debug_otp:
            info_message = f"{info_message}\n\nTest OTP: {debug_otp}"
        self._set_feedback(info_message, "success")
        self._show_popup("OTP Resent", info_message)
        self.start_timer()


Builder.load_string(KV)
