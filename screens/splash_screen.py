from __future__ import annotations

from kivy.clock import Clock
from kivy.lang import Builder
from kivy.metrics import dp, sp
from kivy.properties import StringProperty
from kivymd.app import MDApp

from core.config import config as app_config
from core.navigation import navigate
from core.responsive_screen import ResponsiveScreen

STARTUP_ROUTE_DELAY_SECONDS = float(app_config.startup_splash_seconds)

KV = """
#:import dp kivy.metrics.dp
#:import sp kivy.metrics.sp
#:set BG (0.03, 0.03, 0.05, 1)
#:set BG_SOFT (0.19, 0.14, 0.08, 0.22)
#:set SURFACE (0.08, 0.09, 0.12, 0.96)
#:set SURFACE_SOFT (0.11, 0.12, 0.16, 0.90)
#:set GOLD (0.94, 0.79, 0.46, 1)
#:set GOLD_SOFT (0.93, 0.78, 0.40, 0.40)
#:set TEXT_MAIN (0.95, 0.95, 0.95, 1)
#:set TEXT_SUB (0.74, 0.76, 0.80, 1)
<SplashScreen>:
    MDBoxLayout:
        orientation: "vertical"
        canvas.before:
            Color:
                rgba: BG
            Rectangle:
                pos: self.pos
                size: self.size
            Color:
                rgba: 0.37, 0.28, 0.12, 0.16
            Ellipse:
                pos: self.x - self.width * 0.08, self.top - self.width * 0.54
                size: self.width * 0.72, self.width * 0.72
            Color:
                rgba: 0.20, 0.29, 0.24, 0.18
            Ellipse:
                pos: self.right - self.width * 0.58, self.y + self.height * 0.18
                size: self.width * 0.70, self.width * 0.70
            Color:
                rgba: BG_SOFT
            RoundedRectangle:
                pos: self.x - dp(18), self.y + dp(24)
                size: self.width + dp(36), self.height * 0.60
                radius: [dp(36), dp(36), 0, 0]

        AnchorLayout:
            anchor_x: "center"
            anchor_y: "center"
            padding: [dp(18 * root.layout_scale), dp(24 * root.layout_scale), dp(18 * root.layout_scale), dp(24 * root.layout_scale)]

            MDBoxLayout:
                orientation: "vertical"
                adaptive_height: True
                spacing: dp(14 * root.layout_scale)
                size_hint_x: None
                width: min(root.width - dp(36 * root.layout_scale), dp(420 if not root.tablet_mode else 500))

                MDCard:
                    size_hint_y: None
                    height: dp(188 * root.layout_scale)
                    radius: [dp(28 * root.layout_scale)]
                    padding: [dp(18 * root.layout_scale)] * 4
                    md_bg_color: SURFACE
                    elevation: 0

                    MDBoxLayout:
                        orientation: "vertical"
                        spacing: dp(10 * root.layout_scale)

                        AnchorLayout:
                            size_hint_y: None
                            height: dp(104 * root.layout_scale)
                            anchor_x: "center"
                            anchor_y: "center"

                            FloatLayout:
                                size_hint: None, None
                                size: dp(96 * root.layout_scale), dp(96 * root.layout_scale)
                                canvas.before:
                                    Color:
                                        rgba: 0.94, 0.79, 0.46, 0.11
                                    RoundedRectangle:
                                        pos: self.pos
                                        size: self.size
                                        radius: [dp(26 * root.layout_scale)]
                                    Color:
                                        rgba: GOLD_SOFT
                                    Line:
                                        rounded_rectangle: (self.x, self.y, self.width, self.height, dp(26 * root.layout_scale))
                                        width: dp(max(1.2, 1.6 * root.layout_scale))

                                MDIcon:
                                    icon: "shield-lock-outline"
                                    theme_text_color: "Custom"
                                    text_color: GOLD
                                    font_size: sp(52 * root.icon_scale)
                                    size_hint: None, None
                                    size: dp(72 * root.layout_scale), dp(72 * root.layout_scale)
                                    text_size: self.size
                                    halign: "center"
                                    valign: "center"
                                    pos_hint: {"center_x": 0.5, "center_y": 0.5}

                        MDBoxLayout:
                            size_hint_y: None
                            height: "1dp"
                            canvas.before:
                                Color:
                                    rgba: GOLD_SOFT
                                Rectangle:
                                    pos: self.pos
                                    size: self.size

                        MDLabel:
                            text: "Secure BTC wallet, MoMo payments, and protected transfers in one place."
                            theme_text_color: "Custom"
                            text_color: TEXT_MAIN
                            font_size: sp(14 * root.text_scale)

                MDCard:
                    adaptive_height: True
                    radius: [dp(24 * root.layout_scale)]
                    padding: [dp(18 * root.layout_scale)] * 4
                    md_bg_color: SURFACE_SOFT
                    elevation: 0

                    MDBoxLayout:
                        orientation: "vertical"
                        adaptive_height: True
                        spacing: dp(14 * root.layout_scale)

                        MDLabel:
                            text: "Starting secure session"
                            halign: "center"
                            theme_text_color: "Custom"
                            text_color: TEXT_MAIN
                            bold: True
                            font_size: sp(17 * root.text_scale)

                        MDBoxLayout:
                            adaptive_height: True
                            spacing: dp(10 * root.layout_scale)
                            size_hint_x: 1
                            pos_hint: {"center_x": 0.5}

                            MDCard:
                                adaptive_height: True
                                padding: [dp(10 * root.layout_scale), dp(8 * root.layout_scale)]
                                radius: [dp(16 * root.layout_scale)]
                                md_bg_color: [0.16, 0.18, 0.22, 0.94]
                                size_hint_x: 1
                                elevation: 0

                                MDLabel:
                                    text: "BTC"
                                    halign: "center"
                                    theme_text_color: "Custom"
                                    text_color: GOLD
                                    bold: True
                                    font_size: sp(12.5 * root.text_scale)

                            MDCard:
                                adaptive_height: True
                                padding: [dp(10 * root.layout_scale), dp(8 * root.layout_scale)]
                                radius: [dp(16 * root.layout_scale)]
                                md_bg_color: [0.16, 0.18, 0.22, 0.94]
                                size_hint_x: 1
                                elevation: 0

                                MDLabel:
                                    text: "MoMo"
                                    halign: "center"
                                    theme_text_color: "Custom"
                                    text_color: GOLD
                                    bold: True
                                    font_size: sp(12.5 * root.text_scale)

                            MDCard:
                                adaptive_height: True
                                padding: [dp(10 * root.layout_scale), dp(8 * root.layout_scale)]
                                radius: [dp(16 * root.layout_scale)]
                                md_bg_color: [0.16, 0.18, 0.22, 0.94]
                                size_hint_x: 1
                                elevation: 0

                                MDLabel:
                                    text: "Auth"
                                    halign: "center"
                                    theme_text_color: "Custom"
                                    text_color: GOLD
                                    bold: True
                                    font_size: sp(12.5 * root.text_scale)

                        MDBoxLayout:
                            orientation: "vertical"
                            adaptive_height: True
                            spacing: dp(10 * root.layout_scale)

                            AnchorLayout:
                                size_hint: None, None
                                size: dp(72 * root.layout_scale), dp(72 * root.layout_scale)
                                pos_hint: {"center_x": 0.5}
                                anchor_x: "center"
                                anchor_y: "center"

                                Widget:
                                    size_hint: None, None
                                    size: dp(64 * root.layout_scale), dp(64 * root.layout_scale)
                                    canvas.before:
                                        Color:
                                            rgba: GOLD_SOFT
                                        Line:
                                            circle: (self.center_x, self.center_y, min(self.width, self.height) / 2 - dp(4))
                                            width: dp(max(2.0, 3.0 * root.layout_scale))
                                        Color:
                                            rgba: GOLD
                                        Line:
                                            circle: (self.center_x, self.center_y, min(self.width, self.height) / 2 - dp(10), 20, 320)
                                            width: dp(max(3.0, 4.5 * root.layout_scale))

                            MDLabel:
                                text: root.status_text
                                halign: "center"
                                theme_text_color: "Custom"
                                text_color: TEXT_SUB
                                font_size: sp(13.5 * root.text_scale)

                        MDLabel:
                            text: "Optimized for phone and tablet layouts."
                            halign: "center"
                            theme_text_color: "Custom"
                            text_color: GOLD
                            font_size: sp(12 * root.text_scale)
"""


class SplashScreen(ResponsiveScreen):
    status_text = StringProperty("Securing wallet channels...")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._next_event = None
        self._pulse_event = None
        self._status_frames = [
            "Securing wallet channels",
            "Syncing account services",
            "Preparing dashboard tools",
        ]
        self._status_index = 0
        self._dot_count = 0

    def on_enter(self, *_args):
        self._cancel_events()
        self._status_index = 0
        self._dot_count = 0
        self.status_text = f"{self._status_frames[0]}..."
        self._pulse_event = Clock.schedule_interval(self._animate_status, 0.4)
        app = MDApp.get_running_app()
        request_startup_route = getattr(app, "request_startup_route", None)
        if request_startup_route:
            request_startup_route()
        else:
            self._next_event = Clock.schedule_once(self._complete_startup, STARTUP_ROUTE_DELAY_SECONDS)

    def on_leave(self, *_args):
        self._cancel_events()

    def _cancel_events(self) -> None:
        if self._pulse_event is not None:
            self._pulse_event.cancel()
            self._pulse_event = None
        if self._next_event is not None:
            self._next_event.cancel()
            self._next_event = None

    def _animate_status(self, _dt):
        self._dot_count = (self._dot_count + 1) % 4
        if self._dot_count == 0:
            self._status_index = (self._status_index + 1) % len(self._status_frames)
        dots = "." * max(1, self._dot_count)
        self.status_text = f"{self._status_frames[self._status_index]}{dots}"

    def _complete_startup(self, *_args) -> None:
        app = MDApp.get_running_app()
        complete_startup = getattr(app, "complete_startup", None)
        if complete_startup:
            if complete_startup():
                self._cancel_events()
                return
            request_startup_route = getattr(app, "request_startup_route", None)
            if request_startup_route:
                request_startup_route(delay=STARTUP_ROUTE_DELAY_SECONDS * 2)
                return
            self.status_text = "Retrying secure session..."
            self._next_event = Clock.schedule_once(
                self._complete_startup,
                min(STARTUP_ROUTE_DELAY_SECONDS * 2, 1.0),
            )
            return
        if self.manager and self.manager.has_screen("login"):
            navigate(self.manager, "login", fallback="", transition_style="fade")


Builder.load_string(KV)
