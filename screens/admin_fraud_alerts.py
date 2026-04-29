from __future__ import annotations

from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import StringProperty
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel

from core.screen_actions import ActionScreen

KV = """
#:import dp kivy.metrics.dp
#:import sp kivy.metrics.sp
#:set BG (0.03, 0.04, 0.06, 1)
#:set SURFACE (0.08, 0.10, 0.14, 0.95)
#:set GOLD (0.94, 0.79, 0.46, 1)
#:set TEXT_SUB (0.74, 0.76, 0.80, 1)

<AdminFraudAlertsScreen>:
    MDBoxLayout:
        orientation: "vertical"

        canvas.before:
            Color:
                rgba: app.ui_background
            Rectangle:
                pos: self.pos
                size: self.size

        MDBoxLayout:
            size_hint_y: None
            height: dp(54 * root.layout_scale)
            padding: [dp(16 * root.layout_scale), dp(14 * root.layout_scale), dp(16 * root.layout_scale), 0]

            MDLabel:
                text: "Fraud Alerts"
                font_style: "Title"
                font_size: sp(22 * root.text_scale)
                bold: True
                theme_text_color: "Custom"
                text_color: app.gold

            MDTextButton:
                text: "Back"
                theme_text_color: "Custom"
                text_color: app.gold
                on_release: root.go_back()

        ScrollView:
            do_scroll_x: False
            bar_width: 0

            MDBoxLayout:
                orientation: "vertical"
                adaptive_height: True
                padding: [dp(16 * root.layout_scale), dp(10 * root.layout_scale), dp(16 * root.layout_scale), dp(16 * root.layout_scale)]
                spacing: dp(12 * root.layout_scale)

                MDCard:
                    md_bg_color: app.ui_surface
                    radius: [dp(18 * root.layout_scale)]
                    elevation: 0
                    padding: [dp(12 * root.layout_scale)] * 4
                    adaptive_height: True

                    MDLabel:
                        text: root.placeholder_text
                        theme_text_color: "Custom"
                        text_color: app.ui_text_secondary
                        halign: "center"
                        adaptive_height: True

                Widget:
                    size_hint_y: None
                    height: dp(8 * root.layout_scale)

        MDLabel:
            text: root.feedback_text
            theme_text_color: "Custom"
            text_color: root.feedback_color
            adaptive_height: True
            padding: [dp(16 * root.layout_scale), 0, dp(16 * root.layout_scale), dp(4 * root.layout_scale)]

        BottomNavBar:
            nav_variant: "admin"
            active_target: ""
            layout_scale: root.layout_scale
            text_scale: root.text_scale
            icon_scale: root.icon_scale
            bar_color: app.ui_surface
            active_color: app.gold
            inactive_color: app.ui_text_secondary
"""


class AdminFraudAlertsScreen(ActionScreen):
    placeholder_text = StringProperty("No fraud alerts configured yet.\\n\\nTip: Use Transaction Monitor + device/IP metadata to flag suspicious activity.")


Builder.load_string(KV)
