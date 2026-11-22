import threading
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import StringProperty, BooleanProperty
from kivymd.app import MDApp
from core.responsive_screen import ResponsiveScreen
from core.popup_manager import show_message_dialog
from core.message_sanitizer import extract_backend_message
from api.auth import request_reset_pin_otp, reset_pin
from utils.network import normalize_ghana_number

KV = """
#:import dp kivy.metrics.dp
#:set BG (0.03, 0.04, 0.06, 1)
#:set GOLD (0.94, 0.79, 0.46, 1)
<ResetPinScreen>:
    MDBoxLayout:
        orientation: "vertical"
        padding: dp(20)
        spacing: dp(15)
        canvas.before:
            Color:
                rgba: BG
            Rectangle:
                pos: self.pos
                size: self.size

        MDLabel:
            text: "Reset Your PIN"
            font_style: "H5"
            theme_text_color: "Custom"
            text_color: GOLD
            halign: "center"

        MDTextField:
            id: momo_input
            hint_text: "MoMo Number"
            mode: "rectangle"

        MDRaisedButton:
            text: root.timer_text
            pos_hint: {"center_x": .5}
            on_release: root.request_otp()
            disabled: root.processing or not root.can_resend

        MDTextField:
            id: otp_input
            hint_text: "OTP from email"
            mode: "rectangle"
            opacity: 1 if root.otp_sent else 0

        MDBoxLayout:
            adaptive_height: True
            spacing: dp(8)
            opacity: 1 if root.otp_sent else 0
            disabled: not root.otp_sent

            MDTextField:
                id: new_pin_input
                hint_text: "New 4-digit PIN"
                mode: "rectangle"
                password: True
                max_text_length: 4

            MDIconButton:
                icon: "eye-off"
                theme_text_color: "Custom"
                text_color: GOLD
                pos_hint: {"center_y": .5}
                on_release:
                    new_pin_input.password = not new_pin_input.password
                    self.icon = "eye" if not new_pin_input.password else "eye-off"

        MDRaisedButton:
            text: "Change PIN"
            pos_hint: {"center_x": .5}
            on_release: root.submit_reset()
            opacity: 1 if root.otp_sent else 0
            disabled: root.processing

        MDTextButton:
            text: "Back to Login"
            pos_hint: {"center_x": .5}
            on_release: app.go_to_screen("login")
"""

class ResetPinScreen(ResponsiveScreen):
    content_max_width = 430.0
    processing = BooleanProperty(False)
    otp_sent = BooleanProperty(False)
    timer_text = StringProperty("Request Reset OTP")
    can_resend = BooleanProperty(True)
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.countdown = 60
        self.timer_event = None
        self._active = False
        self._request_generation = 0
        self._request_inflight = False
        self._request_inflight_generation = None

    def on_enter(self, *_args):
        self._active = True
        self._request_generation += 1
        self.processing = self._request_inflight

    def on_leave(self, *_args):
        self._active = False
        self._request_generation += 1
        if self.timer_event is not None:
            self.timer_event.cancel()
            self.timer_event = None
        for field_name in ("otp_input", "new_pin_input"):
            field = self.ids.get(field_name)
            if field is not None:
                field.text = ""
        parent_on_leave = getattr(super(), "on_leave", None)
        if callable(parent_on_leave):
            return parent_on_leave(*_args)

    def start_timer(self):
        self.countdown = 60
        self.can_resend = False
        if self.timer_event:
            self.timer_event.cancel()
        self.timer_event = Clock.schedule_interval(self.update_timer, 1)

    def update_timer(self, dt):
        self.countdown -= 1
        if self.countdown <= 0:
            if self.timer_event:
                self.timer_event.cancel()
                self.timer_event = None
            self.timer_text = "Resend Reset OTP"
            self.can_resend = True
            return False
        self.timer_text = f"Resend in {self.countdown}s"
        return True

    def request_otp(self):
        if self.processing:
            return
        momo = normalize_ghana_number(self.ids.momo_input.text.strip())
        if not momo or len(momo) != 10 or not momo.startswith("0"):
            show_message_dialog(self, "Check your number", "Enter the 10-digit MoMo number linked to your account.")
            return

        self.ids.momo_input.text = momo
        self.processing = True
        generation = self._request_generation
        self._request_inflight = True
        self._request_inflight_generation = generation

        def _worker():
            try:
                response = request_reset_pin_otp(momo)
            except Exception:
                response = {"ok": False, "data": {"detail": "We could not reach the service. Check your connection and try again."}}
            Clock.schedule_once(lambda dt: self._on_otp_result(response, generation))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_otp_result(self, response, generation: int | None = None):
        if not self._active or generation != self._request_generation:
            if generation == self._request_inflight_generation:
                self._request_inflight = False
                self._request_inflight_generation = None
                self.processing = False
            return
        self._request_inflight = False
        self._request_inflight_generation = None
        self.processing = False
        ok = bool(response.get("ok")) if isinstance(response, dict) else False
        if ok:
            self.otp_sent = True
            self.start_timer()
            show_message_dialog(self, "Check your email", "We sent a PIN reset code to the email saved on your account.")
        else:
            payload = response.get("data", response) if isinstance(response, dict) else response
            detail = extract_backend_message(
                payload,
                fallback="We could not send the reset code. Check the number and saved email, then try again.",
            )
            show_message_dialog(
                self,
                "Reset code not sent",
                detail,
            )

    def submit_reset(self):
        if self.processing:
            return
        momo = normalize_ghana_number(self.ids.momo_input.text.strip())
        otp = self.ids.otp_input.text.strip()
        new_pin = self.ids.new_pin_input.text.strip()
        if not momo or len(momo) != 10 or not momo.startswith("0"):
            show_message_dialog(self, "Check your number", "Enter the 10-digit MoMo number linked to your account.")
            return
        if len(otp) != 6 or not otp.isdigit():
            show_message_dialog(self, "Check the code", "Enter the 6-digit code sent to your email.")
            return
        if len(new_pin) != 4 or not new_pin.isdigit():
            show_message_dialog(self, "Check your new PIN", "Your new PIN must contain exactly 4 digits.")
            return

        self.processing = True
        generation = self._request_generation
        self._request_inflight = True
        self._request_inflight_generation = generation

        def _worker():
            try:
                response = reset_pin(momo, otp, new_pin)
            except Exception:
                response = {"ok": False, "data": {"detail": "We could not reach the service. Check your connection and try again."}}
            Clock.schedule_once(lambda dt: self._on_reset_finish(response, generation))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_reset_finish(self, response, generation: int | None = None):
        if not self._active or generation != self._request_generation:
            if generation == self._request_inflight_generation:
                self._request_inflight = False
                self._request_inflight_generation = None
                self.processing = False
            return
        self._request_inflight = False
        self._request_inflight_generation = None
        self.processing = False
        if isinstance(response, dict) and response.get("ok"):
            show_message_dialog(self, "Success", "PIN reset successfully. You can now login.", 
                                on_close=lambda gen=generation: self._continue_to_login(gen))
            return

        payload = response.get("data", response) if isinstance(response, dict) else response
        detail = extract_backend_message(payload, fallback="We could not reset your PIN. Check the code and try again.")
        show_message_dialog(self, "PIN not changed", detail)

    def _continue_to_login(self, generation: int) -> None:
        if not self._active or generation != self._request_generation:
            return
        app = MDApp.get_running_app()
        go_to_screen = getattr(app, "go_to_screen", None)
        if callable(go_to_screen):
            go_to_screen("login", fallback="", transition_style="fade")
        elif self.manager:
            from core.navigation import navigate

            navigate(self.manager, "login", fallback="", transition_style="fade")

Builder.load_string(KV)
