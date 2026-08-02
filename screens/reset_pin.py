import threading
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import StringProperty, BooleanProperty
from kivymd.app import MDApp
from core.responsive_screen import ResponsiveScreen
from core.popup_manager import show_message_dialog
from api.auth import resend_otp # Using shared logic for OTP request
import requests
from api.client import API_URL

KV = """
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
            hint_text: "OTP from SMS"
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
    processing = BooleanProperty(False)
    otp_sent = BooleanProperty(False)
    timer_text = StringProperty("Request Reset OTP")
    can_resend = BooleanProperty(True)
    countdown = 60
    timer_event = None

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
        momo = self.ids.momo_input.text.strip()
        if not momo: return
        self.processing = True
        self.start_timer()
        def _worker():
            try:
                # Correct backend endpoint for reset-pin flow
                resp = requests.post(f"{API_URL}/auth/reset-pin/request-otp", json={"momo_number": momo})
                ok = resp.status_code == 200
            except: ok = False
            Clock.schedule_once(lambda dt: self._on_otp_result(ok))
        threading.Thread(target=_worker, daemon=True).start()

    def _on_otp_result(self, ok):
        self.processing = False
        if ok:
            self.otp_sent = True
            show_message_dialog(self, "OTP Sent", "Check your messages for the reset code.")
        else:
            show_message_dialog(self, "Error", "Could not request reset. Check your number.")

    def submit_reset(self):
        momo = self.ids.momo_input.text.strip()
        otp = self.ids.otp_input.text.strip()
        new_pin = self.ids.new_pin_input.text.strip()
        self.processing = True
        def _worker():
            try:
                resp = requests.post(f"{API_URL}/auth/reset-pin", json={
                    "momo_number": momo, "otp": otp, "new_pin": new_pin
                })
                ok = resp.status_code == 200
            except: ok = False
            Clock.schedule_once(lambda dt: self._on_reset_finish(ok))
        threading.Thread(target=_worker, daemon=True).start()

    def _on_reset_finish(self, ok):
        self.processing = False
        if ok:
            show_message_dialog(self, "Success", "PIN reset successfully. You can now login.", 
                                on_close=lambda: MDApp.get_running_app().go_to_screen("login"))

Builder.load_string(KV)
