import threading
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import StringProperty, BooleanProperty
from kivymd.app import MDApp
from kivymd.uix.fitimage import FitImage
from core.responsive_screen import ResponsiveScreen
from core.popup_manager import show_message_dialog
from core.auth_assets import asset_path
from api.auth import request_reset_pin_otp, reset_pin

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
<ResetPinScreen>:
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
                                    text: "Reset Your PIN"
                                    theme_text_color: "Custom"
                                    text_color: TEXT_MAIN
                                    bold: True
                                    font_size: sp(25 * root.text_scale)
                                    text_size: self.width, None
                                    halign: "left"
                                    size_hint_y: None
                                    height: self.texture_size[1] if self.text else 0

                                MDLabel:
                                    text: "Request an OTP, then choose a new 4-digit PIN"
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

                                    MDLabel:
                                        text: "PIN Reset"
                                        theme_text_color: "Custom"
                                        text_color: GOLD
                                        bold: True
                                        font_size: sp(17 * root.text_scale)
                                        size_hint_x: None
                                        width: self.texture_size[0]
                                        size_hint_y: None
                                        height: self.texture_size[1] if self.text else 0

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
                                                text: "Secure reset"
                                                theme_text_color: "Custom"
                                                text_color: TEXT_MAIN
                                                font_size: sp(7.6 * root.text_scale)
                                                size_hint_y: None
                                                height: self.texture_size[1] if self.text else 0

                                            MDLabel:
                                                text: "PIN"
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
                                helper_text: "Enter the same MoMo number used for your account."
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

                        MDFillRoundFlatIconButton:
                            text: root.timer_text
                            icon: "timer-outline"
                            md_bg_color: GOLD_SOFT
                            text_color: BG
                            size_hint_y: None
                            height: dp(58 * root.layout_scale)
                            on_release: root.request_otp()
                            disabled: root.processing or not root.can_resend

                        MDTextField:
                            id: otp_input
                            hint_text: "OTP from SMS"
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
                            opacity: 1 if root.otp_sent else 0
                            height: dp(70 * root.layout_scale) if root.otp_sent else 0
                            size_hint_y: None

                        MDBoxLayout:
                            adaptive_height: True
                            spacing: dp(10 * root.layout_scale)
                            opacity: 1 if root.otp_sent else 0
                            disabled: not root.otp_sent
                            size_hint_y: None
                            height: dp(70 * root.layout_scale) if root.otp_sent else 0

                            MDIconButton:
                                icon: "shield-key-outline"
                                theme_text_color: "Custom"
                                text_color: GOLD
                                user_font_size: str(22 * root.icon_scale) + "sp"
                                size_hint: None, None
                                size: dp(36 * root.layout_scale), dp(36 * root.layout_scale)
                                disabled: True

                            MDTextField:
                                id: new_pin_input
                                hint_text: "New 4-digit PIN"
                                helper_text: "Choose a new 4-digit PIN."
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
                                password: True
                                max_text_length: 4
                                size_hint_x: 1

                            MDIconButton:
                                icon: "eye-off"
                                theme_text_color: "Custom"
                                text_color: GOLD
                                pos_hint: {"center_y": .5}
                                on_release:
                                    new_pin_input.password = not new_pin_input.password
                                    self.icon = "eye" if not new_pin_input.password else "eye-off"

                        MDFillRoundFlatIconButton:
                            text: "Change PIN"
                            icon: "check-circle-outline"
                            md_bg_color: GOLD_SOFT
                            text_color: BG
                            size_hint_y: None
                            height: dp(58 * root.layout_scale) if root.otp_sent else 0
                            on_release: root.submit_reset()
                            opacity: 1 if root.otp_sent else 0
                            disabled: root.processing

                        MDTextButton:
                            text: "Back to Login"
                            pos_hint: {"center_x": .5}
                            theme_text_color: "Custom"
                            text_color: GOLD
                            on_release: app.go_to_screen("login")
"""

class ResetPinScreen(ResponsiveScreen):
    content_max_width = 430.0
    processing = BooleanProperty(False)
    otp_sent = BooleanProperty(False)
    timer_text = StringProperty("Request Reset OTP")
    can_resend = BooleanProperty(True)
    countdown = 60
    timer_event = None
    hero_source = StringProperty("")
    card_art_source = StringProperty("")
    brand_tagline = StringProperty("YOUR MONEY. YOUR GOAL. YOUR WORLD.")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.hero_source = asset_path("cybercash_logo.png")
        self.card_art_source = asset_path("cybercash_icon.png")

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
            response = request_reset_pin_otp(momo)
            ok = bool(response.get("ok")) if isinstance(response, dict) else False
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
            response = reset_pin(momo, otp, new_pin)
            ok = bool(response.get("ok")) if isinstance(response, dict) else False
            Clock.schedule_once(lambda dt: self._on_reset_finish(ok))
        threading.Thread(target=_worker, daemon=True).start()

    def _on_reset_finish(self, ok):
        self.processing = False
        if ok:
            show_message_dialog(self, "Success", "PIN reset successfully. You can now login.", 
                                on_close=lambda: MDApp.get_running_app().go_to_screen("login"))

Builder.load_string(KV)
