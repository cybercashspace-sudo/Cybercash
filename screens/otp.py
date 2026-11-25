import threading

from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import BooleanProperty, ColorProperty, StringProperty
from kivymd.app import MDApp

from api.auth import resend_otp, verify_account
from components.app_snackbar import show_app_snackbar
from core.message_sanitizer import extract_backend_message
from core.navigation import navigate
from core.popup_manager import show_message_dialog
from core.responsive_screen import ResponsiveScreen
from core.session import session
from utils.network import normalize_ghana_number

DEFAULT_OTP_FEEDBACK_TEXT = "Enter the 6-digit OTP we sent to your email to complete secure access."

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

        PullRefreshScrollView:
            root_layout: root
            refresh_callback: root.pull_to_refresh
            spinner_color: app.gold
            circle_color: app.ui_background
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

                            MDCard:
                                size_hint: None, None
                                size: dp(56 * root.layout_scale), dp(56 * root.layout_scale)
                                radius: [dp(18 * root.layout_scale)]
                                md_bg_color: SURFACE_SOFT
                                elevation: 0
                                padding: 0
                                pos_hint: {"center_y": 0.5}

                                MDIconButton:
                                    icon: "shield-check-outline"
                                    icon_size: str(28 * root.icon_scale) + "sp"
                                    size_hint: None, None
                                    size: dp(32 * root.layout_scale), dp(32 * root.layout_scale)
                                    pos_hint: {"center_x": 0.5, "center_y": 0.5}
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
                            text: "Verify your email to continue securely."
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

                        MDLabel:
                            text: "Enter the 6-digit code sent to your registered email."
                            theme_text_color: "Custom"
                            text_color: TEXT_SUB
                            font_size: sp(12 * root.text_scale)
                            adaptive_height: True

                        MDTextField:
                            id: momo_input
                            hint_text: "MoMo number"
                            mode: "rectangle"
                            icon_right: "phone"
                            line_color_focus: GOLD
                            multiline: False

                        MDLabel:
                            text: "Use the same number linked to your account."
                            theme_text_color: "Custom"
                            text_color: TEXT_SUB
                            font_size: sp(11.5 * root.text_scale)
                            adaptive_height: True

                        MDTextField:
                            id: otp_input
                            hint_text: "6-digit OTP"
                            mode: "rectangle"
                            icon_right: "shield-key-outline"
                            line_color_focus: GOLD
                            max_text_length: 6
                            input_filter: "int"
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
                            text: "Verify and Continue"
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
                            on_release: app.go_to_screen("login")
"""


class OTPScreen(ResponsiveScreen):
    content_max_width = 430.0

    timer_text = StringProperty("You can request a new OTP in 120s")
    can_resend = BooleanProperty(False)
    feedback_text = StringProperty(DEFAULT_OTP_FEEDBACK_TEXT)
    feedback_color = ColorProperty([0.72, 0.74, 0.79, 1])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.momo_number = None
        self.countdown = 120
        self.timer_event = None
        self._verifying = False
        self._resending = False
        self._verify_inflight_generation = None
        self._resend_inflight_generation = None
        self._active = False
        self._screen_generation = 0
        self._dashboard_route_event = None
        self._dashboard_route_attempts = 0

    def _set_feedback(self, message: str, level: str = "info"):
        palette = {
            "info": [0.72, 0.74, 0.79, 1],
            "success": [0.54, 0.82, 0.67, 1],
            "warning": [0.94, 0.80, 0.46, 1],
            "error": [0.96, 0.46, 0.41, 1],
        }
        self.feedback_text = str(message or "").strip()
        self.feedback_color = palette.get(level, palette["info"])

    def _show_popup(self, title: str, message: str, on_close=None, close_label: str = "Close"):
        show_message_dialog(
            self,
            title=title,
            message=message,
            close_label=close_label,
            on_close=on_close,
        )

    def _go_home(self):
        app = MDApp.get_running_app()
        go_to_screen = getattr(app, "go_to_screen", None)
        pending_action = str(getattr(app, "pending_wallet_action", "") or "").strip().lower()
        if pending_action == "deposit":
            app.wallet_entry_action = "deposit"
            if go_to_screen and go_to_screen("deposit", fallback="wallet"):
                self._dashboard_route_attempts = 0
                return True
        if go_to_screen:
            routed = bool(go_to_screen("home", fallback="", transition_style="fade"))
        elif self.manager:
            routed = bool(navigate(self.manager, "home", fallback="", transition_style="fade"))
        else:
            routed = False

        if routed:
            self._dashboard_route_attempts = 0
            return True

        # Navigation may still be completing the OTP screen transition. Retry
        # briefly instead of leaving a verified user stranded on the OTP page.
        if self._active and self._dashboard_route_attempts < 8 and self._dashboard_route_event is None:
            self._dashboard_route_attempts += 1
            self._dashboard_route_event = Clock.schedule_once(self._retry_dashboard_route, 0.18)
        return False

    def _retry_dashboard_route(self, _dt) -> None:
        self._dashboard_route_event = None
        if self._active:
            self._go_home()

    @staticmethod
    def _extract_detail(response: dict) -> str:
        return extract_backend_message(response)

    def on_enter(self, *_args):
        self._active = True
        self._screen_generation += 1
        if self.momo_number:
            self.ids.momo_input.text = self.momo_number
            self._set_feedback(
                "We sent a 6-digit OTP to your email. Enter it below to continue.",
                "info",
            )
        else:
            self._set_feedback(DEFAULT_OTP_FEEDBACK_TEXT, "info")
        self.start_timer()

    def on_leave(self, *_args):
        self._active = False
        self._screen_generation += 1
        if self._dashboard_route_event is not None:
            self._dashboard_route_event.cancel()
            self._dashboard_route_event = None
        self._dashboard_route_attempts = 0
        if self.timer_event:
            self.timer_event.cancel()
            self.timer_event = None
        for field_name in ("otp_input", "momo_input"):
            field = self.ids.get(field_name)
            if field is not None:
                field.text = ""
        self.momo_number = None
        app = MDApp.get_running_app()
        if app is not None and hasattr(app, "pending_momo"):
            app.pending_momo = ""
        parent_on_leave = getattr(super(), "on_leave", None)
        if callable(parent_on_leave):
            return parent_on_leave(*_args)

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
        self._verify_inflight_generation = self._screen_generation

        threading.Thread(
            target=self._verify_worker,
            args=(momo, otp, self._screen_generation),
            daemon=True,
        ).start()

    def _verify_worker(self, momo: str, otp: str, generation: int):
        try:
            response = verify_account(momo, otp)
        except Exception as exc:
            response = {"detail": str(exc) or "Verification failed."}
        Clock.schedule_once(lambda _dt: self._apply_verify_response(response, generation))

    def _apply_verify_response(self, response: dict, generation: int | None = None):
        if not self._active or generation != self._screen_generation:
            if generation == self._verify_inflight_generation:
                self._verifying = False
                self._verify_inflight_generation = None
            return
        self._verifying = False
        self._verify_inflight_generation = None
        app = MDApp.get_running_app()

        if isinstance(response, dict) and str(response.get("status", "")).strip().lower() == "verified":
            token = str(response.get("access_token", "") or "").strip()
            if not token:
                error_message = "Your account was verified, but sign-in could not be completed. Please sign in to continue."
                self._set_feedback(error_message, "error")
                self._show_popup(
                    "Verification Complete",
                    error_message,
                    close_label="Go to Sign In",
                    on_close=self._go_to_login,
                )
                return

            first_name = str(response.get("first_name", "") or "").strip()
            user_payload = response.get("user") if isinstance(response.get("user"), dict) else {}
            if first_name and not user_payload.get("first_name"):
                user_payload = {**user_payload, "first_name": first_name}
            # Clear any previous account's cached expiry/profile before adopting
            # this newly authenticated token, so session state cannot disagree.
            session.clear_auth()
            session.start_session(token, user=user_payload or None)
            app.access_token = token
            app.pending_momo = ""
            app.user_name = first_name or getattr(app, "user_name", "Cyber Cash User")
            app_state = getattr(app, "app_state", None)
            if app_state is not None and user_payload:
                app_state.set_user(user_payload)
            self._set_feedback("Verification successful. Opening your dashboard…", "success")
            self._go_home()
            try:
                show_app_snackbar("Your account is verified. Welcome to CyberCash.", level="success")
            except Exception:
                pass
            return

        error_message = self._extract_detail(response) or "Verification failed."
        self._set_feedback(error_message, "error")
        self._show_popup("Verification Failed", error_message)

    def _go_to_login(self, *_args) -> None:
        app = MDApp.get_running_app()
        go_to_screen = getattr(app, "go_to_screen", None)
        if callable(go_to_screen):
            go_to_screen("login", fallback="", transition_style="fade")
        elif self.manager:
            navigate(self.manager, "login", fallback="", transition_style="fade")

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
        self._resend_inflight_generation = self._screen_generation
        threading.Thread(
            target=self._resend_worker,
            args=(momo, self._screen_generation),
            daemon=True,
        ).start()

    def _resend_worker(self, momo: str, generation: int):
        try:
            response = resend_otp(momo)
        except Exception as exc:
            response = {"detail": str(exc) or "Unable to resend OTP right now."}
        Clock.schedule_once(lambda _dt: self._apply_resend_response(response, generation))

    def _apply_resend_response(self, response: dict, generation: int | None = None):
        if not self._active or generation != self._screen_generation:
            if generation == self._resend_inflight_generation:
                self._resending = False
                self._resend_inflight_generation = None
            return
        self._resending = False
        self._resend_inflight_generation = None
        if not isinstance(response, dict) or response.get("detail"):
            error_message = self._extract_detail(response) or "Unable to resend OTP right now."
            self._set_feedback(error_message, "error")
            self._show_popup("Resend Failed", error_message)
            return

        info_message = self._extract_detail(response) or "A new OTP has been sent to your email address."
        self._set_feedback(info_message, "success")
        self._show_popup("OTP Resent", info_message)
        self.start_timer()


Builder.load_string(KV)
