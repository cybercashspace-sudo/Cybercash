import threading

from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import BooleanProperty, ColorProperty, StringProperty
from kivymd.app import MDApp
from kivymd.uix.fitimage import FitImage

from api.auth import resend_otp, verify_account
from core.auth_assets import asset_path
from core.message_sanitizer import extract_backend_message
from core.navigation import navigate
from core.popup_manager import show_message_dialog
from core.responsive_screen import ResponsiveScreen
from storage import save_token
from utils.network import normalize_ghana_number

DEFAULT_OTP_FEEDBACK_TEXT = "Enter the 6-digit OTP we sent to your phone to complete secure access."

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
                                    text: "Verify Account"
                                    theme_text_color: "Custom"
                                    text_color: TEXT_MAIN
                                    bold: True
                                    font_size: sp(25 * root.text_scale)
                                    text_size: self.width, None
                                    halign: "left"
                                    size_hint_y: None
                                    height: self.texture_size[1] if self.text else 0

                                MDLabel:
                                    text: "Enter the 6-digit code sent to continue securely."
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
                                            text: "OTP"
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
                                        icon: "shield-check-outline"
                                        theme_text_color: "Custom"
                                        text_color: GOLD
                                        user_font_size: str(23 * root.icon_scale) + "sp"
                                        size_hint: None, None
                                        size: dp(34 * root.layout_scale), dp(34 * root.layout_scale)
                                        pos_hint: {"right": 0.98, "top": 0.98}
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
                                                text: "OTP verification"
                                                theme_text_color: "Custom"
                                                text_color: TEXT_MAIN
                                                font_size: sp(7.6 * root.text_scale)
                                                size_hint_y: None
                                                height: self.texture_size[1] if self.text else 0

                                            MDLabel:
                                                text: "SECURE"
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
                                helper_text: "Use the same MoMo number you used earlier."
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
                                icon: "shield-key-outline"
                                theme_text_color: "Custom"
                                text_color: GOLD
                                user_font_size: str(22 * root.icon_scale) + "sp"
                                size_hint: None, None
                                size: dp(36 * root.layout_scale), dp(36 * root.layout_scale)
                                disabled: True

                            MDTextField:
                                id: otp_input
                                hint_text: "OTP"
                                helper_text: "Enter the 6-digit code exactly as received."
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
                                max_text_length: 6
                                multiline: False

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
                            text: "Verify OTP"
                            icon: "check-circle-outline"
                            md_bg_color: GOLD_SOFT
                            text_color: BG
                            size_hint_y: None
                            height: dp(58 * root.layout_scale)
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
                            on_release: app.go_to_screen("login")
"""


class OTPScreen(ResponsiveScreen):
    content_max_width = 430.0
    momo_number = None
    countdown = 120
    timer_event = None
    _verifying = False
    _resending = False

    timer_text = StringProperty("You can request a new OTP in 120s")
    can_resend = BooleanProperty(False)
    feedback_text = StringProperty(DEFAULT_OTP_FEEDBACK_TEXT)
    feedback_color = ColorProperty([0.72, 0.74, 0.79, 1])
    hero_source = StringProperty("")
    card_art_source = StringProperty("")
    brand_tagline = StringProperty("YOUR MONEY. YOUR GOAL. YOUR WORLD.")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.hero_source = asset_path("cybercash_logo.png")
        self.card_art_source = asset_path("cybercash_icon.png")

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

    def _go_home(self):
        app = MDApp.get_running_app()
        go_to_screen = getattr(app, "go_to_screen", None)
        pending_action = str(getattr(app, "pending_wallet_action", "") or "").strip().lower()
        if pending_action == "deposit":
            app.wallet_entry_action = "deposit"
            if go_to_screen and go_to_screen("deposit", fallback="wallet"):
                return
        if go_to_screen:
            go_to_screen("home", fallback="login", transition_style="fade")
            return
        if self.manager:
            navigate(self.manager, "home", fallback="login", transition_style="fade")

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
        if self._verifying:
            return

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
        self._verifying = True

        threading.Thread(target=self._verify_worker, args=(momo, otp), daemon=True).start()

    def _verify_worker(self, momo: str, otp: str):
        try:
            response = verify_account(momo, otp)
        except Exception as exc:
            response = {"detail": str(exc) or "Verification failed."}
        Clock.schedule_once(lambda _dt: self._apply_verify_response(response))

    def _apply_verify_response(self, response: dict):
        self._verifying = False
        app = MDApp.get_running_app()

        if isinstance(response, dict) and str(response.get("status", "")).strip().lower() == "verified":
            token = str(response.get("access_token", "") or "")
            first_name = str(response.get("first_name", "") or "").strip()
            save_token(token)
            app.access_token = token
            app.pending_momo = first_name or ""
            app.user_name = first_name or getattr(app, "user_name", "Cyber Cash User")
            self._set_feedback("Verification successful.", "success")
            self._show_popup(
                "Verification Successful",
                "Your account is verified and ready to use.",
                on_close=self._go_home,
            )
            return

        error_message = self._extract_detail(response) or "Verification failed."
        self._set_feedback(error_message, "error")
        self._show_popup("Verification Failed", error_message)

    def resend(self):
        if self._resending:
            return

        momo = normalize_ghana_number((self.ids.momo_input.text or self.momo_number or "").strip())
        if not self.can_resend:
            self._show_popup("Please Wait", "Please wait for the timer to finish before requesting another OTP.")
            return
        if not momo or len(momo) != 10 or not momo.startswith("0"):
            self._set_feedback("Enter a valid MoMo number to resend OTP.", "error")
            self._show_popup("Invalid Number", "Please enter a valid MoMo number to resend OTP.")
            return

        self._set_feedback("Resending OTP...", "info")
        self._resending = True
        threading.Thread(target=self._resend_worker, args=(momo,), daemon=True).start()

    def _resend_worker(self, momo: str):
        try:
            response = resend_otp(momo)
        except Exception as exc:
            response = {"detail": str(exc) or "Unable to resend OTP right now."}
        Clock.schedule_once(lambda _dt: self._apply_resend_response(response))

    def _apply_resend_response(self, response: dict):
        self._resending = False
        if not isinstance(response, dict) or response.get("detail"):
            error_message = self._extract_detail(response) or "Unable to resend OTP right now."
            self._set_feedback(error_message, "error")
            self._show_popup("Resend Failed", error_message)
            return

        info_message = self._extract_detail(response) or "A new OTP has been sent to your MoMo number."
        self._set_feedback(info_message, "success")
        self._show_popup("OTP Resent", info_message)
        self.start_timer()


Builder.load_string(KV)
