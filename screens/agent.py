import json
import threading
from datetime import datetime, timezone

import requests
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.metrics import dp, sp
from kivy.properties import BooleanProperty, ListProperty, NumericProperty, StringProperty
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.gridlayout import GridLayout
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDFillRoundFlatIconButton, MDIconButton
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivymd.uix.textfield import MDTextField

from api.client import API_URL
from core.message_sanitizer import extract_backend_message, sanitize_backend_message
from core.popup_manager import show_custom_dialog, show_message_dialog
from core.responsive_screen import ResponsiveScreen
from utils.network import detect_network, normalize_ghana_number

FONT_REGULAR = "kivy_frontend/assets/fonts/Inter-Regular.ttf"
FONT_SEMIBOLD = "kivy_frontend/assets/fonts/Inter-SemiBold.ttf"
FONT_BOLD = "kivy_frontend/assets/fonts/Inter-Bold.ttf"
TX_CARD_BG = [0.09, 0.10, 0.12, 0.88]
POSITIVE_COLOR = [0.61, 0.88, 0.72, 1]
NEGATIVE_COLOR = [0.98, 0.48, 0.41, 1]
TOPUP_FEE_RATE = 0.05
WITHDRAWAL_FEE_RATE = 0.01

KV = """
#:import dp kivy.metrics.dp
#:import sp kivy.metrics.sp
#:set BG (0.02, 0.02, 0.03, 1)
#:set BG_SOFT (0.24, 0.18, 0.11, 0.18)
#:set SURFACE (0.09, 0.10, 0.12, 0.84)
#:set SURFACE_SOFT (0.12, 0.14, 0.14, 0.88)
#:set GREEN_CARD (0.17, 0.30, 0.24, 0.96)
#:set GREEN_BTN (0.17, 0.28, 0.23, 0.96)
#:set GOLD (0.95, 0.80, 0.47, 1)
#:set GOLD_SOFT (0.92, 0.74, 0.36, 0.98)
#:set TEXT_MAIN (0.94, 0.93, 0.89, 1)
#:set TEXT_SUB (0.72, 0.72, 0.74, 1)
#:set FONT_REG "kivy_frontend/assets/fonts/Inter-Regular.ttf"
#:set FONT_SEMI "kivy_frontend/assets/fonts/Inter-SemiBold.ttf"
#:set FONT_BOLD "kivy_frontend/assets/fonts/Inter-Bold.ttf"
<AgentScreen>:
    MDBoxLayout:
        orientation: "vertical"

        canvas.before:
            Color:
                rgba: BG
            Rectangle:
                pos: self.pos
                size: self.size
            Color:
                rgba: 0.40, 0.31, 0.15, 0.10
            Ellipse:
                pos: self.x + self.width * 0.20, self.y + self.height * 0.77
                size: self.width * 0.56, self.width * 0.56
            Color:
                rgba: 0.25, 0.39, 0.31, 0.20
            Ellipse:
                pos: self.x + self.width * 0.30, self.y + self.height * 0.48
                size: self.width * 0.70, self.width * 0.70
            Color:
                rgba: 0.18, 0.13, 0.08, 0.10
            Ellipse:
                pos: self.x + self.width * 0.10, self.y - self.height * 0.02
                size: self.width * 0.54, self.width * 0.54
            Color:
                rgba: BG_SOFT
            RoundedRectangle:
                pos: self.x - dp(20), self.y + dp(36)
                size: self.width + dp(40), self.height * 0.62
                radius: [dp(42), dp(42), dp(16), dp(16)]
            Color:
                rgba: 1, 1, 1, 0.035
            RoundedRectangle:
                pos: self.x + dp(10), self.y + dp(10)
                size: self.width - dp(20), self.height - dp(20)
                radius: [dp(38)]

        ScrollView:
            do_scroll_x: False
            bar_width: 0

            MDBoxLayout:
                orientation: "vertical"
                size_hint_y: None
                height: self.minimum_height
                size_hint_x: None
                width: min((self.parent.width if self.parent else root.width), dp(430))
                pos_hint: {"center_x": 0.5}
                padding: [dp(16 * root.layout_scale), dp(14 * root.layout_scale), dp(16 * root.layout_scale), dp(16 * root.layout_scale)]
                spacing: dp(11 * root.layout_scale)

                MDBoxLayout:
                    size_hint_y: None
                    height: dp(62 * root.layout_scale)

                    MDCard:
                        size_hint: None, None
                        size: dp(52 * root.layout_scale), dp(52 * root.layout_scale)
                        radius: [dp(26 * root.layout_scale)]
                        md_bg_color: 0.11, 0.12, 0.14, 0.90
                        line_color: [0.36, 0.31, 0.24, 0.34]
                        elevation: 0
                        on_release: root.go_to_settings()

                        AnchorLayout:
                            anchor_x: "center"
                            anchor_y: "center"

                            MDIconButton:
                                icon: "account-circle"
                                user_font_size: str(30 * root.icon_scale) + "sp"
                                size_hint: None, None
                                size: dp(30 * root.layout_scale), dp(30 * root.layout_scale)
                                theme_text_color: "Custom"
                                text_color: GOLD
                                on_release: root.go_to_settings()

                    MDLabel:
                        text: "AGENT DASHBOARD"
                        halign: "center"
                        bold: True
                        font_style: "Title"
                        font_name: FONT_BOLD
                        font_size: sp(22 * root.text_scale)
                        theme_text_color: "Custom"
                        text_color: GOLD

                    FloatLayout:
                        size_hint: None, None
                        size: dp(44 * root.layout_scale), dp(54 * root.layout_scale)

                        MDIconButton:
                            icon: "bell-ring-outline"
                            user_font_size: str(24 * root.icon_scale) + "sp"
                            size_hint: None, None
                            size: dp(24 * root.layout_scale), dp(24 * root.layout_scale)
                            pos_hint: {"center_x": 0.5, "center_y": 0.5}
                            theme_text_color: "Custom"
                            text_color: 0.94, 0.79, 0.49, 1
                            on_release: root.show_notifications()

                        MDCard:
                            size_hint: None, None
                            size: dp(18 * root.layout_scale), dp(18 * root.layout_scale)
                            radius: [dp(9 * root.layout_scale)]
                            md_bg_color: 0.86, 0.18, 0.14, 1
                            pos_hint: {"center_x": 0.74, "center_y": 0.78}
                            elevation: 0

                            MDLabel:
                                text: "1"
                                halign: "center"
                                valign: "middle"
                                theme_text_color: "Custom"
                                text_color: 1, 1, 1, 1
                                font_size: sp(10 * root.text_scale)
                                bold: True

                MDBoxLayout:
                    size_hint_y: None
                    height: "1dp"
                    canvas.before:
                        Color:
                            rgba: 0.48, 0.49, 0.52, 0.24
                        Rectangle:
                            pos: self.pos
                            size: self.size
                        Color:
                            rgba: 0.90, 0.75, 0.42, 0.24
                        Rectangle:
                            pos: self.center_x - self.width * 0.26, self.y - dp(1)
                            size: self.width * 0.52, dp(3)
                        Color:
                            rgba: 0.95, 0.81, 0.49, 0.90
                        Rectangle:
                            pos: self.center_x - self.width * 0.18, self.y
                            size: self.width * 0.36, self.height

                MDCard:
                    size_hint_y: None
                    height: dp(52 * root.layout_scale)
                    radius: [dp(14 * root.layout_scale)]
                    md_bg_color: SURFACE
                    line_color: [0.33, 0.31, 0.27, 0.42]
                    elevation: 0
                    padding: [dp(10 * root.layout_scale), dp(6 * root.layout_scale), dp(12 * root.layout_scale), dp(6 * root.layout_scale)]

                    MDBoxLayout:
                        spacing: dp(8 * root.layout_scale)

                        MDCard:
                            size_hint: None, None
                            size: dp(34 * root.layout_scale), dp(34 * root.layout_scale)
                            radius: [dp(11 * root.layout_scale)]
                            md_bg_color: 0.62, 0.48, 0.22, 0.48
                            elevation: 0

                            AnchorLayout:
                                anchor_x: "center"
                                anchor_y: "center"

                                MDIconButton:
                                    icon: "account-tie"
                                    user_font_size: str(18 * root.icon_scale) + "sp"
                                    size_hint: None, None
                                    size: dp(22 * root.layout_scale), dp(22 * root.layout_scale)
                                    theme_text_color: "Custom"
                                    text_color: 0.94, 0.78, 0.44, 1
                                    disabled: True

                        MDLabel:
                            text: root.greeting_text
                            font_style: "Body"
                            font_name: FONT_SEMI
                            font_size: sp(16 * root.text_scale)
                            theme_text_color: "Custom"
                            text_color: TEXT_MAIN
                            shorten: True
                            shorten_from: "right"

                        Widget:

                        MDCard:
                            size_hint: None, None
                            size: dp(92 * root.layout_scale), dp(26 * root.layout_scale)
                            radius: [dp(13 * root.layout_scale)]
                            md_bg_color: root.agent_status_bg_color
                            elevation: 0

                            MDLabel:
                                text: root.agent_status_display
                                halign: "center"
                                valign: "middle"
                                theme_text_color: "Custom"
                                text_color: root.agent_status_text_color
                                font_size: sp(11.5 * root.text_scale)
                                bold: True

                MDCard:
                    radius: [dp(22 * root.layout_scale)]
                    md_bg_color: GREEN_CARD
                    line_color: [0.44, 0.63, 0.54, 0.50]
                    elevation: 0
                    padding: [dp(16 * root.layout_scale), dp(16 * root.layout_scale), dp(16 * root.layout_scale), dp(16 * root.layout_scale)]
                    size_hint_y: None
                    height: dp(196 * root.layout_scale)

                    canvas.before:
                        Color:
                            rgba: 0.27, 0.46, 0.37, 0.34
                        RoundedRectangle:
                            pos: self.x + dp(1), self.y + dp(1)
                            size: self.width - dp(2), self.height - dp(2)
                            radius: [dp(20)]
                        Color:
                            rgba: 0.82, 0.98, 0.75, 0.08
                        RoundedRectangle:
                            pos: self.x + dp(14), self.top - self.height * 0.34
                            size: self.width * 0.72, self.height * 0.24
                            radius: [dp(22)]
                        Color:
                            rgba: 0.05, 0.10, 0.10, 0.28
                        RoundedRectangle:
                            pos: self.center_x - dp(8), self.y + dp(10)
                            size: self.width * 0.62, self.height * 0.52
                            radius: [dp(34), dp(14), dp(24), dp(12)]

                    MDBoxLayout:
                        orientation: "vertical"
                        spacing: dp(6 * root.layout_scale)

                        MDBoxLayout:
                            size_hint_y: None
                            height: dp(42 * root.layout_scale)
                            spacing: dp(10 * root.layout_scale)

                            MDCard:
                                size_hint: None, None
                                size: dp(34 * root.layout_scale), dp(34 * root.layout_scale)
                                radius: [dp(11 * root.layout_scale)]
                                md_bg_color: 0.44, 0.66, 0.34, 0.92
                                elevation: 0

                                AnchorLayout:
                                    anchor_x: "center"
                                    anchor_y: "center"

                                    MDIconButton:
                                        icon: "wallet-outline"
                                        user_font_size: str(18 * root.icon_scale) + "sp"
                                        size_hint: None, None
                                        size: dp(22 * root.layout_scale), dp(22 * root.layout_scale)
                                        theme_text_color: "Custom"
                                        text_color: 0.91, 0.98, 0.83, 1
                                        disabled: True

                            MDLabel:
                                text: "Agent Float Balance"
                                bold: True
                                font_style: "Body"
                                font_name: FONT_SEMI
                                font_size: sp(15 * root.text_scale)
                                theme_text_color: "Custom"
                                text_color: TEXT_MAIN
                                valign: "middle"

                            MDCard:
                                size_hint: None, None
                                size: dp(34 * root.layout_scale), dp(34 * root.layout_scale)
                                radius: [dp(17 * root.layout_scale)]
                                md_bg_color: 0.12, 0.22, 0.19, 0.62
                                line_color: [0.55, 0.73, 0.62, 0.22]
                                elevation: 0

                                AnchorLayout:
                                    anchor_x: "center"
                                    anchor_y: "center"

                                    MDIconButton:
                                        icon: "eye-off-outline" if root.balance_hidden else "eye-outline"
                                        user_font_size: str(18 * root.icon_scale) + "sp"
                                        size_hint: None, None
                                        size: dp(24 * root.layout_scale), dp(24 * root.layout_scale)
                                        theme_text_color: "Custom"
                                        text_color: 0.90, 0.96, 0.84, 1
                                        on_release: root.toggle_balance()

                        MDLabel:
                            text: root.balance_display
                            bold: True
                            font_style: "Headline"
                            font_name: FONT_BOLD
                            font_size: sp(34 * root.text_scale)
                            theme_text_color: "Custom"
                            text_color: 0.96, 0.84, 0.53, 1

                        MDLabel:
                            text: "Float " + root.float_display + " | Commission " + root.commission_display
                            font_style: "Body"
                            font_name: FONT_REG
                            font_size: sp(12 * root.text_scale)
                            theme_text_color: "Custom"
                            text_color: TEXT_MAIN
                            shorten: True
                            shorten_from: "right"

                        MDLabel:
                            text: "Commission Rate " + root.agent_commission_rate_display + " | Recoverable " + root.recovery_display
                            font_style: "Body"
                            font_name: FONT_REG
                            font_size: sp(11.5 * root.text_scale)
                            theme_text_color: "Custom"
                            text_color: TEXT_SUB
                            shorten: True
                            shorten_from: "right"

                        MDLabel:
                            text: root.status_text
                            font_style: "Body"
                            font_name: FONT_REG
                            font_size: sp(10.5 * root.text_scale)
                            theme_text_color: "Custom"
                            text_color: TEXT_SUB
                            shorten: True
                            shorten_from: "right"

                        MDLabel:
                            text: root.funding_note
                            font_style: "Body"
                            font_name: FONT_REG
                            font_size: sp(10 * root.text_scale)
                            theme_text_color: "Custom"
                            text_color: 0.92, 0.77, 0.43, 1
                            shorten: True
                            shorten_from: "right"

                MDBoxLayout:
                    size_hint_y: None
                    height: dp(84 * root.layout_scale)
                    spacing: dp(10 * root.layout_scale)

                    MDCard:
                        radius: [dp(20 * root.layout_scale)]
                        md_bg_color: app.gold
                        line_color: [0.97, 0.86, 0.62, 0.76]
                        elevation: 0
                        padding: [dp(10 * root.layout_scale), dp(8 * root.layout_scale), dp(14 * root.layout_scale), dp(8 * root.layout_scale)]
                        on_release: root.open_fund_user_dialog()
                        canvas.before:
                            Color:
                                rgba: 1, 0.95, 0.78, 0.15
                            RoundedRectangle:
                                pos: self.x + dp(2), self.top - self.height * 0.34
                                size: self.width - dp(4), self.height * 0.24
                                radius: [dp(18)]

                        MDBoxLayout:
                            spacing: dp(10 * root.layout_scale)

                            MDCard:
                                size_hint: None, None
                                size: dp(38 * root.layout_scale), dp(38 * root.layout_scale)
                                radius: [dp(11 * root.layout_scale)]
                                md_bg_color: 0.58, 0.40, 0.15, 0.56
                                elevation: 0

                                AnchorLayout:
                                    anchor_x: "center"
                                    anchor_y: "center"

                                    MDIconButton:
                                        icon: "wallet-plus"
                                        user_font_size: str(20 * root.icon_scale) + "sp"
                                        size_hint: None, None
                                        size: dp(22 * root.layout_scale), dp(22 * root.layout_scale)
                                        theme_text_color: "Custom"
                                        text_color: 0.23, 0.17, 0.08, 1
                                        disabled: True

                            MDLabel:
                                text: "Fund"
                                bold: True
                                valign: "middle"
                                font_style: "Title"
                                font_name: FONT_BOLD
                                font_size: sp(16 * root.text_scale)
                                theme_text_color: "Custom"
                                text_color: 0, 0, 0, 1

                    MDCard:
                        radius: [dp(20 * root.layout_scale)]
                        md_bg_color: GREEN_BTN
                        line_color: [0.59, 0.79, 0.66, 0.54]
                        elevation: 0
                        padding: [dp(10 * root.layout_scale), dp(8 * root.layout_scale), dp(14 * root.layout_scale), dp(8 * root.layout_scale)]
                        on_release: root.open_cash_withdraw_dialog()
                        canvas.before:
                            Color:
                                rgba: 0.86, 0.96, 0.86, 0.08
                            RoundedRectangle:
                                pos: self.x + dp(2), self.top - self.height * 0.32
                                size: self.width - dp(4), self.height * 0.22
                                radius: [dp(18)]

                        MDBoxLayout:
                            spacing: dp(10 * root.layout_scale)

                            MDCard:
                                size_hint: None, None
                                size: dp(38 * root.layout_scale), dp(38 * root.layout_scale)
                                radius: [dp(11 * root.layout_scale)]
                                md_bg_color: 0.10, 0.24, 0.19, 0.82
                                elevation: 0

                                AnchorLayout:
                                    anchor_x: "center"
                                    anchor_y: "center"

                                    MDIconButton:
                                        icon: "cash-fast"
                                        user_font_size: str(20 * root.icon_scale) + "sp"
                                        size_hint: None, None
                                        size: dp(22 * root.layout_scale), dp(22 * root.layout_scale)
                                        theme_text_color: "Custom"
                                        text_color: 0.78, 0.93, 0.77, 1
                                        disabled: True

                            MDLabel:
                                text: "Withdraw"
                                bold: True
                                valign: "middle"
                                font_style: "Title"
                                font_name: FONT_BOLD
                                font_size: sp(16 * root.text_scale)
                                theme_text_color: "Custom"
                                text_color: TEXT_MAIN

                MDBoxLayout:
                    adaptive_height: True

                    MDLabel:
                        text: "Quick Actions"
                        font_style: "Title"
                        font_name: FONT_BOLD
                        font_size: sp(20 * root.text_scale)
                        theme_text_color: "Custom"
                        text_color: GOLD

                    MDTextButton:
                        text: "View All"
                        theme_text_color: "Custom"
                        text_color: 0.92, 0.77, 0.43, 1
                        font_size: sp(15 * root.text_scale)
                        on_release: root.go_to_transactions()

                MDGridLayout:
                    cols: root.quick_action_cols
                    adaptive_height: True
                    row_default_height: dp(112 * root.layout_scale)
                    row_force_default: True
                    spacing: dp(9 * root.layout_scale)

                    MDCard:
                        radius: [dp(16 * root.layout_scale)]
                        md_bg_color: 0.10, 0.17, 0.15, 0.82
                        line_color: [0.31, 0.48, 0.41, 0.42]
                        elevation: 0
                        padding: [dp(4 * root.layout_scale)] * 4
                        on_release: root.open_data_bundle_dialog()
                        MDBoxLayout:
                            orientation: "vertical"
                            spacing: "0dp"
                            AnchorLayout:
                                anchor_x: "center"
                                anchor_y: "center"
                                size_hint_y: None
                                height: dp(34 * root.layout_scale)

                                MDIconButton:
                                    icon: "wifi"
                                    user_font_size: str(30 * root.icon_scale) + "sp"
                                    size_hint: None, None
                                    size: dp(30 * root.layout_scale), dp(30 * root.layout_scale)
                                    theme_text_color: "Custom"
                                    text_color: 0.55, 0.84, 0.66, 1
                                    on_release: root.open_data_bundle_dialog()
                            MDLabel:
                                text: "Bundles"
                                halign: "center"
                                font_name: FONT_SEMI
                                font_size: sp(12 * root.text_scale)
                                theme_text_color: "Custom"
                                text_color: TEXT_MAIN

                    MDCard:
                        radius: [dp(16 * root.layout_scale)]
                        md_bg_color: 0.10, 0.18, 0.15, 0.82
                        line_color: [0.35, 0.50, 0.41, 0.42]
                        elevation: 0
                        padding: [dp(4 * root.layout_scale)] * 4
                        on_release: root.open_recovery_dialog()
                        MDBoxLayout:
                            orientation: "vertical"
                            spacing: "0dp"
                            AnchorLayout:
                                anchor_x: "center"
                                anchor_y: "center"
                                size_hint_y: None
                                height: dp(34 * root.layout_scale)

                                MDIconButton:
                                    icon: "history"
                                    user_font_size: str(30 * root.icon_scale) + "sp"
                                    size_hint: None, None
                                    size: dp(30 * root.layout_scale), dp(30 * root.layout_scale)
                                    theme_text_color: "Custom"
                                    text_color: 0.91, 0.75, 0.44, 1
                                    on_release: root.open_recovery_dialog()
                            MDLabel:
                                text: "Recovery"
                                halign: "center"
                                font_name: FONT_SEMI
                                font_size: sp(12 * root.text_scale)
                                theme_text_color: "Custom"
                                text_color: TEXT_MAIN

                    MDCard:
                        radius: [dp(16 * root.layout_scale)]
                        md_bg_color: 0.10, 0.16, 0.14, 0.82
                        line_color: [0.34, 0.48, 0.40, 0.38]
                        elevation: 0
                        padding: [dp(4 * root.layout_scale)] * 4
                        on_release: root.load_transactions()
                        MDBoxLayout:
                            orientation: "vertical"
                            spacing: "0dp"
                            AnchorLayout:
                                anchor_x: "center"
                                anchor_y: "center"
                                size_hint_y: None
                                height: dp(34 * root.layout_scale)

                                MDIconButton:
                                    icon: "phone-forward"
                                    user_font_size: str(30 * root.icon_scale) + "sp"
                                    size_hint: None, None
                                    size: dp(30 * root.layout_scale), dp(30 * root.layout_scale)
                                    theme_text_color: "Custom"
                                    text_color: 0.83, 0.92, 0.60, 1
                                    on_release: root.open_sell_airtime_dialog()
                            MDLabel:
                                text: "Sell Airtime"
                                halign: "center"
                                font_name: FONT_SEMI
                                font_size: sp(12 * root.text_scale)
                                theme_text_color: "Custom"
                                text_color: TEXT_MAIN

                    MDCard:
                        radius: [dp(16 * root.layout_scale)]
                        md_bg_color: 0.16, 0.14, 0.10, 0.82
                        line_color: [0.53, 0.41, 0.23, 0.40]
                        elevation: 0
                        padding: [dp(4 * root.layout_scale)] * 4
                        on_release: root.open_more_actions()
                        MDBoxLayout:
                            orientation: "vertical"
                            spacing: "0dp"
                            AnchorLayout:
                                anchor_x: "center"
                                anchor_y: "center"
                                size_hint_y: None
                                height: dp(34 * root.layout_scale)

                                MDIconButton:
                                    icon: "view-grid"
                                    user_font_size: str(30 * root.icon_scale) + "sp"
                                    size_hint: None, None
                                    size: dp(30 * root.layout_scale), dp(30 * root.layout_scale)
                                    theme_text_color: "Custom"
                                    text_color: 0.90, 0.75, 0.43, 1
                                    on_release: root.open_more_actions()
                            MDLabel:
                                text: "More"
                                halign: "center"
                                font_name: FONT_SEMI
                                font_size: sp(12 * root.text_scale)
                                theme_text_color: "Custom"
                                text_color: TEXT_MAIN

                MDBoxLayout:
                    adaptive_height: True

                    MDLabel:
                        text: "Recent Activity"
                        font_style: "Title"
                        font_name: FONT_BOLD
                        font_size: sp(20 * root.text_scale)
                        theme_text_color: "Custom"
                        text_color: TEXT_MAIN

                    MDTextButton:
                        text: "View All"
                        theme_text_color: "Custom"
                        text_color: 0.92, 0.77, 0.43, 1
                        font_size: sp(15 * root.text_scale)
                        on_release: root.go_to_transactions()

                MDBoxLayout:
                    id: recent_container
                    orientation: "vertical"
                    adaptive_height: True
                    spacing: dp(10 * root.layout_scale)

                MDBoxLayout:
                    adaptive_height: True
                    spacing: dp(8 * root.layout_scale)
                    size_hint_x: None
                    width: dp(88 * root.layout_scale)
                    pos_hint: {"center_x": 0.5}

                    Widget:
                        canvas.before:
                            Color:
                                rgba: 0.93, 0.77, 0.44, 1
                            RoundedRectangle:
                                pos: self.x + dp(2), self.center_y - dp(2)
                                size: self.width - dp(4), dp(4)
                                radius: [dp(2)]

                    Widget:
                        canvas.before:
                            Color:
                                rgba: 0.43, 0.44, 0.38, 0.58
                            RoundedRectangle:
                                pos: self.x + dp(2), self.center_y - dp(2)
                                size: self.width - dp(4), dp(4)
                                radius: [dp(2)]

                    Widget:
                        canvas.before:
                            Color:
                                rgba: 0.43, 0.44, 0.38, 0.58
                            RoundedRectangle:
                                pos: self.x + dp(2), self.center_y - dp(2)
                                size: self.width - dp(4), dp(4)
                                radius: [dp(2)]

                Widget:
                    size_hint_y: None
                    height: dp(8 * root.layout_scale)

        BottomNavBar:
            nav_variant: "agent"
            active_target: "agent"
            layout_scale: root.layout_scale
            text_scale: root.text_scale
            icon_scale: root.icon_scale
            bar_color: [0.05, 0.07, 0.09, 0.98]
            active_color: GOLD
            inactive_color: [0.65, 0.82, 0.71, 1]
"""


class AgentScreen(ResponsiveScreen):
    greeting_text = StringProperty("Hello, Agent")
    status_text = StringProperty("Last sync: --")
    funding_note = StringProperty("")
    float_display = StringProperty("GHS 0.00")
    commission_display = StringProperty("GHS 0.00")
    recovery_display = StringProperty("0 item(s)")
    balance_hidden = BooleanProperty(False)
    balance_display = StringProperty("GHS 0.00")
    agent_total_balance = NumericProperty(0.0)
    total_transactions_label = StringProperty("0 total")
    agent_status_display = StringProperty("--")
    agent_commission_rate_display = StringProperty("--")
    agent_commission_rate_value = NumericProperty(0.0)
    agent_id_display = StringProperty("--")
    agent_status_bg_color = ListProperty([0.12, 0.14, 0.18, 0.95])
    agent_status_text_color = ListProperty([0.86, 0.88, 0.90, 1])
    _last_warning_popup = ""
    _action_popup = None
    _more_actions_dialog = None
    _recovery_payload = None

    def on_pre_enter(self):
        self.load_transactions()

    def on_leave(self):
        self._close_more_actions_dialog()

    def toggle_balance(self):
        self.balance_hidden = not self.balance_hidden
        self._update_balance_display()

    def _update_balance_display(self):
        if self.balance_hidden:
            self.balance_display = "GHS ****.**"
        else:
            self.balance_display = f"GHS {float(self.agent_total_balance or 0.0):,.2f}"

    def _update_greeting(self):
        agent_id = str(self.agent_id_display or "").strip()
        status = str(self.agent_status_display or "").strip()
        if agent_id and agent_id != "--":
            if status and status != "--":
                self.greeting_text = f"Agent {agent_id} | {status}"
            else:
                self.greeting_text = f"Agent {agent_id}"
        elif status and status != "--":
            self.greeting_text = f"{status} Agent"
        else:
            self.greeting_text = "Hello, Agent"

    @staticmethod
    def _format_amount(amount: float) -> str:
        value = float(amount or 0.0)
        if abs(value - int(value)) < 1e-9:
            return f"{int(value):,}"
        return f"{value:,.2f}"

    def _friendly_type(self, tx_type: str) -> str:
        key = str(tx_type or "").strip().lower()
        mapping = {
            "agent_deposit": "Fund User",
            "agent_withdrawal": "Cash Withdrawal",
            "agent_airtime_sale": "Airtime Sale",
            "agent_data_bundle_sale": "Data Bundle Sale",
            "funding": "Paystack Deposit",
        }
        return mapping.get(key, key.replace("_", " ").title() if key else "Transaction")

    def _friendly_time(self, timestamp: str) -> str:
        raw = str(timestamp or "").strip()
        if not raw:
            return "Today"
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            tx_day = parsed.astimezone(timezone.utc).date()
            if tx_day == now.date():
                return "Today"
            if (now.date() - tx_day).days == 1:
                return "Yesterday"
            return parsed.strftime("%d %b")
        except Exception:
            return "Recent"

    @staticmethod
    def _extract_detail(payload: object) -> str:
        return extract_backend_message(payload)

    @staticmethod
    def _normalize_network_label(network: str) -> str:
        value = str(network or "").strip().upper()
        if value in {"VODAFONE", "TELECEL"}:
            return "TELECEL"
        if value in {"AIRTEL", "TIGO", "AIRTELTIGO", "AIRTEL TIGO"}:
            return "AIRTELTIGO"
        if value == "MTN":
            return "MTN"
        return value

    def _set_status_chip(self, status_key: str) -> None:
        key = str(status_key or "").strip().lower()
        if key in {"active", "approved"}:
            self.agent_status_bg_color = [0.24, 0.43, 0.34, 0.96]
            self.agent_status_text_color = [0.94, 0.99, 0.96, 1]
            return
        if key in {"pending", "processing", "review", "awaiting_approval"}:
            self.agent_status_bg_color = [0.93, 0.77, 0.39, 1]
            self.agent_status_text_color = [0.07, 0.08, 0.10, 1]
            return
        if key in {"inactive", "blocked", "suspended", "rejected"}:
            self.agent_status_bg_color = [0.45, 0.18, 0.18, 0.96]
            self.agent_status_text_color = [0.98, 0.88, 0.88, 1]
            return
        self.agent_status_bg_color = [0.12, 0.14, 0.18, 0.95]
        self.agent_status_text_color = [0.86, 0.88, 0.90, 1]

    def _close_action_dialog(self) -> None:
        dialog = getattr(self, "_action_popup", None) or getattr(self, "_active_dialog", None)
        if dialog:
            try:
                dialog.dismiss()
            except Exception:
                pass
        self._action_popup = None

    def _post_agent_action(self, endpoint: str, payload: dict, success_message: str) -> None:
        app = MDApp.get_running_app()
        token = str(getattr(app, "access_token", "") or "").strip()
        if not token:
            show_message_dialog(self, title="Sign In Required", message="Please sign in first.")
            return

        self.status_text = "Submitting agent action..."

        def _worker():
            try:
                resp = requests.post(f"{API_URL}{endpoint}", headers={"Authorization": f"Bearer {token}"}, json=payload, timeout=12)
                data = resp.json() if resp.content else {}
                ok = resp.status_code < 400
                message = success_message if ok else (self._extract_detail(data) or "Request failed.")
            except Exception as exc:
                ok = False
                message = sanitize_backend_message(exc, fallback="Request failed. Please try again.")

            Clock.schedule_once(lambda _dt: self._handle_action_result(ok, message))

        threading.Thread(target=_worker, daemon=True).start()

    def _handle_action_result(self, ok: bool, message: str) -> None:
        self.status_text = message if message else self.status_text
        show_message_dialog(
            self,
            title="Success" if ok else "Action Failed",
            message=message,
            close_label="Close",
        )
        if ok:
            self.load_transactions()

    def _extract_counterparty(self, tx: dict) -> str:
        metadata = {}
        raw = tx.get("metadata_json")
        if isinstance(raw, dict):
            metadata = raw
        elif isinstance(raw, str) and raw.strip():
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    metadata = parsed
            except Exception:
                metadata = {}

        value = (
            metadata.get("customer_phone")
            or metadata.get("customer_email")
            or metadata.get("recipient_phone")
            or metadata.get("recipient_email")
            or "-"
        )
        return str(value)

    @staticmethod
    def _extract_metadata(tx: dict) -> dict:
        raw = tx.get("metadata_json")
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str) and raw.strip():
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                return {}
        return {}

    def _show_warning_popup(self, message: str):
        msg = str(message or "").strip()
        if not msg or msg == self._last_warning_popup:
            return
        self._last_warning_popup = msg
        show_message_dialog(
            self,
            title="Agent Notice",
            message=msg,
            close_label="Close",
        )

    def go_to_transactions(self):
        if self.manager and self.manager.has_screen("transactions"):
            self.manager.current = "transactions"
            return
        show_message_dialog(
            self,
            title="Transactions",
            message="Transactions screen is not available right now.",
            close_label="Close",
        )

    def go_to_settings(self):
        if self.manager and self.manager.has_screen("settings"):
            self.manager.current = "settings"
            return
        show_message_dialog(
            self,
            title="Settings",
            message="Settings screen is not available right now.",
            close_label="Close",
        )

    def show_notifications(self):
        self._show_warning_popup("Agent notifications center is coming soon. Recent activity is shown below.")

    def _close_more_actions_dialog(self, *_args):
        dialog = getattr(self, "_more_actions_dialog", None)
        if dialog is not None:
            try:
                dialog.dismiss()
            except Exception:
                pass
        self._more_actions_dialog = None

    def open_more_actions(self):
        self._close_more_actions_dialog()

        layout_scale = float(self.layout_scale or 1.0)
        text_scale = float(self.text_scale or 1.0)
        icon_scale = float(self.icon_scale or 1.0)
        compact_mode = bool(self.compact_mode)

        menu_content = MDBoxLayout(
            orientation="vertical",
            spacing=dp(10 * layout_scale),
            adaptive_height=True,
            padding=[dp(2), dp(4), dp(2), 0],
        )
        menu_content.add_widget(
            MDLabel(
                text="Choose an agent action",
                adaptive_height=True,
                font_style="Title",
                font_name=FONT_SEMIBOLD,
                font_size=sp(15 * text_scale),
                bold=True,
                theme_text_color="Custom",
                text_color=[0.94, 0.93, 0.90, 1],
            )
        )
        menu_content.add_widget(
            MDLabel(
                text="Top up wallets, manage data bundles, withdraw cash, recover items, refresh balances, or view activity.",
                adaptive_height=True,
                font_style="Body",
                font_name=FONT_REGULAR,
                font_size=sp(11.5 * text_scale),
                theme_text_color="Custom",
                text_color=[0.70, 0.72, 0.77, 1],
            )
        )

        grid = GridLayout(
            cols=1 if compact_mode else 2,
            spacing=dp(10 * layout_scale),
            size_hint_y=None,
        )
        grid.bind(minimum_height=grid.setter("height"))
        grid.row_default_height = dp(114 * layout_scale)
        grid.row_force_default = True

        def add_action_card(
            label: str,
            subtitle: str,
            icon_name: str,
            icon_color: list[float],
            card_bg: list[float],
            card_line: list[float],
            handler,
        ) -> None:
            def _select(*_args):
                self._close_more_actions_dialog()
                handler()

            card = MDCard(
                size_hint=(1, None),
                height=dp(114 * layout_scale),
                radius=[dp(16 * layout_scale)],
                md_bg_color=card_bg,
                line_color=card_line,
                padding=[dp(8 * layout_scale)] * 4,
                elevation=0,
            )
            card.bind(on_release=_select)

            content = MDBoxLayout(orientation="vertical", spacing=dp(3 * layout_scale))
            icon_wrap = AnchorLayout(
                anchor_x="center",
                anchor_y="center",
                size_hint_y=None,
                height=dp(38 * layout_scale),
            )
            icon_btn = MDIconButton(
                icon=icon_name,
                user_font_size=f"{30 * icon_scale:.1f}sp",
                size_hint=(None, None),
                size=(dp(36 * layout_scale), dp(36 * layout_scale)),
                theme_text_color="Custom",
                text_color=icon_color,
            )
            icon_btn.bind(on_release=_select)
            icon_wrap.add_widget(icon_btn)
            content.add_widget(icon_wrap)
            content.add_widget(
                MDLabel(
                    text=label,
                    adaptive_height=True,
                    halign="center",
                    font_style="Title",
                    font_name=FONT_SEMIBOLD,
                    font_size=sp(13 * text_scale),
                    bold=True,
                    theme_text_color="Custom",
                    text_color=[0.94, 0.93, 0.90, 1],
                    shorten=True,
                    shorten_from="right",
                )
            )
            content.add_widget(
                MDLabel(
                    text=subtitle,
                    adaptive_height=True,
                    halign="center",
                    font_style="Body",
                    font_name=FONT_REGULAR,
                    font_size=sp(10.5 * text_scale),
                    theme_text_color="Custom",
                    text_color=[0.70, 0.72, 0.77, 1],
                    shorten=True,
                    shorten_from="right",
                )
            )
            card.add_widget(content)
            grid.add_widget(card)

        add_action_card(
            "Fund",
            "Wallet top-up",
            "wallet-plus",
            [0.94, 0.79, 0.46, 1],
            [0.10, 0.17, 0.15, 0.92],
            [0.31, 0.48, 0.41, 0.42],
            self.open_fund_user_dialog,
        )
        add_action_card(
            "Airtime",
            "Sell airtime",
            "phone-forward",
            [0.72, 0.84, 0.95, 1],
            [0.10, 0.18, 0.18, 0.92],
            [0.32, 0.50, 0.55, 0.42],
            self.open_sell_airtime_dialog,
        )
        add_action_card(
            "Data",
            "Bundle sales",
            "wifi",
            [0.55, 0.84, 0.66, 1],
            [0.10, 0.18, 0.15, 0.92],
            [0.35, 0.50, 0.41, 0.42],
            self.open_data_bundle_dialog,
        )
        add_action_card(
            "Withdraw",
            "Cash payout",
            "cash-fast",
            [0.91, 0.75, 0.44, 1],
            [0.16, 0.14, 0.10, 0.92],
            [0.53, 0.41, 0.23, 0.40],
            self.open_cash_withdraw_dialog,
        )
        add_action_card(
            "Recover",
            "Restore items",
            "history",
            [0.83, 0.92, 0.60, 1],
            [0.09, 0.10, 0.12, 0.92],
            [0.20, 0.23, 0.28, 0.62],
            self.open_recovery_dialog,
        )
        add_action_card(
            "Sync",
            "Update data",
            "refresh",
            [0.90, 0.75, 0.43, 1],
            [0.10, 0.17, 0.15, 0.92],
            [0.31, 0.48, 0.41, 0.42],
            self.load_transactions,
        )
        add_action_card(
            "History",
            "View all",
            "format-list-bulleted",
            [0.94, 0.79, 0.46, 1],
            [0.16, 0.14, 0.10, 0.92],
            [0.53, 0.41, 0.23, 0.40],
            self.go_to_transactions,
        )

        menu_content.add_widget(grid)

        dialog = show_custom_dialog(
            self,
            title="More",
            content_cls=menu_content,
            close_label="Close",
            auto_dismiss=True,
        )
        dialog.bind(on_dismiss=lambda *_args: setattr(self, "_more_actions_dialog", None))
        self._more_actions_dialog = dialog

    def _format_recovery_item(self, item: dict) -> str:
        if not isinstance(item, dict):
            return str(item)
        tx_type = str(item.get("type") or item.get("reason") or "Recovery").replace("_", " ").title()
        status = str(item.get("status") or "pending").replace("_", " ").title()
        timestamp = str(item.get("timestamp") or item.get("created_at") or "")
        when = self._friendly_time(timestamp) if timestamp else "Recent"
        try:
            amount_val = float(item.get("amount") or item.get("value") or 0.0)
        except Exception:
            amount_val = 0.0
        amount_text = f"GHS {self._format_amount(abs(amount_val))}" if amount_val else ""
        reference = str(item.get("reference") or item.get("id") or "").strip()
        parts = [tx_type, status, when]
        if amount_text:
            parts.append(amount_text)
        if reference:
            parts.append(reference)
        return " | ".join(part for part in parts if part)

    def _recover_transaction(self, item: dict) -> None:
        tx_id = None
        if isinstance(item, dict):
            tx_id = item.get("id") or item.get("transaction_id")
        if not tx_id:
            show_message_dialog(
                self,
                title="Recovery",
                message="Recovery is unavailable for this item.",
                close_label="Close",
            )
            return

        self._close_action_dialog()
        self._post_agent_action(
            f"/agent-transactions/me/recover/{tx_id}",
            payload={},
            success_message="Recovery submitted successfully.",
        )

    def open_recovery_dialog(self):
        items = list(self._recovery_payload or [])
        if not items:
            show_message_dialog(
                self,
                title="Recovery",
                message="No recoverable items found right now.",
                close_label="Close",
            )
            return

        layout_scale = float(self.layout_scale or 1.0)
        text_scale = float(self.text_scale or 1.0)

        content = MDBoxLayout(orientation="vertical", spacing=dp(8 * layout_scale), size_hint_y=None)
        content.bind(minimum_height=content.setter("height"))
        content.add_widget(
            MDLabel(
                text=f"{len(items)} recoverable item(s)",
                theme_text_color="Custom",
                text_color=[0.94, 0.79, 0.46, 1],
                font_size=f"{14 * text_scale:.1f}sp",
                bold=True,
                adaptive_height=True,
            )
        )
        for item in items[:8]:
            row = MDBoxLayout(
                orientation="horizontal",
                spacing=dp(8 * layout_scale),
                size_hint_y=None,
                height=dp(40 * layout_scale),
            )
            row.add_widget(
                MDLabel(
                    text=self._format_recovery_item(item),
                    theme_text_color="Custom",
                    text_color=[0.88, 0.90, 0.92, 1],
                    font_size=f"{11 * text_scale:.1f}sp",
                    shorten=True,
                    shorten_from="right",
                )
            )
            tx_id = None
            if isinstance(item, dict):
                tx_id = item.get("id") or item.get("transaction_id")
            recover_button = MDFillRoundFlatIconButton(
                text="Recover" if tx_id else "Unavailable",
                icon="restore",
                md_bg_color=[0.93, 0.77, 0.39, 1],
                text_color=[0.07, 0.08, 0.10, 1],
                size_hint=(None, None),
                height=dp(32 * layout_scale),
            )
            recover_button.width = dp(116 * layout_scale)
            recover_button.disabled = not bool(tx_id)
            recover_button.bind(on_release=lambda *_args, it=item: self._recover_transaction(it))
            row.add_widget(recover_button)
            content.add_widget(row)
        if len(items) > 8:
            content.add_widget(
                MDLabel(
                    text=f"And {len(items) - 8} more...",
                    theme_text_color="Custom",
                    text_color=[0.70, 0.72, 0.77, 1],
                    font_size=f"{11 * text_scale:.1f}sp",
                    adaptive_height=True,
                )
            )

        self._action_popup = show_custom_dialog(
            self,
            title="Recovery",
            content_cls=content,
            close_label="Close",
            auto_dismiss=True,
        )

    def _build_tx_card(self, tx: dict) -> MDCard:
        tx_type = str(tx.get("type", "") or "")
        tx_key = tx_type.lower()
        amount_raw = float(tx.get("amount", 0.0) or 0.0)
        positive = amount_raw >= 0
        if "withdrawal" in tx_key or "cash_withdrawal" in tx_key:
            positive = False
        if "deposit" in tx_key or "sale" in tx_key:
            positive = True
        amount = abs(amount_raw)
        sign = "+" if positive else "-"
        amount_color = POSITIVE_COLOR if positive else NEGATIVE_COLOR
        icon_name = "arrow-top-right" if positive else "arrow-bottom-right"
        status_text = str(tx.get("status", "unknown") or "unknown").replace("_", " ").title()
        when = self._friendly_time(str(tx.get("timestamp", "") or ""))
        counterparty = self._extract_counterparty(tx)
        layout_scale = float(self.layout_scale or 1.0)
        text_scale = float(self.text_scale or 1.0)
        icon_scale = float(self.icon_scale or 1.0)
        icon_bg = [0.21, 0.33, 0.24, 0.94] if positive else [0.33, 0.19, 0.16, 0.94]
        icon_line = [0.50, 0.73, 0.57, 0.34] if positive else [0.86, 0.47, 0.39, 0.28]
        detail_parts = [status_text] if status_text else []
        if counterparty and counterparty != "-":
            detail_parts.append(counterparty)
        detail_text = " | ".join(detail_parts)

        card = MDCard(
            size_hint_y=None,
            height=dp((98 if detail_text else 82) * layout_scale),
            radius=[dp(16 * layout_scale)],
            md_bg_color=TX_CARD_BG,
            padding=[dp(10 * layout_scale), dp(10 * layout_scale), dp(12 * layout_scale), dp(10 * layout_scale)],
            line_color=[0.20, 0.23, 0.28, 0.62],
            elevation=0,
        )
        row = MDBoxLayout(orientation="horizontal", spacing=dp(9 * layout_scale))

        icon_wrap = MDCard(
            size_hint=(None, None),
            size=(dp(44 * layout_scale), dp(44 * layout_scale)),
            radius=[dp(12 * layout_scale)],
            md_bg_color=icon_bg,
            line_color=icon_line,
            elevation=0,
        )
        icon_anchor = AnchorLayout(anchor_x="center", anchor_y="center")
        icon_button = MDIconButton(
            icon=icon_name,
            size_hint=(None, None),
            size=(dp(22 * layout_scale), dp(22 * layout_scale)),
            theme_text_color="Custom",
            text_color=amount_color,
            user_font_size=f"{20 * icon_scale:.1f}sp",
            disabled=True,
        )
        icon_anchor.add_widget(icon_button)
        icon_wrap.add_widget(icon_anchor)

        text_col = MDBoxLayout(orientation="vertical", spacing=dp(2 * layout_scale))
        text_col.add_widget(
            MDLabel(
                text=self._friendly_type(tx_type),
                font_style="Title",
                font_name=FONT_SEMIBOLD,
                font_size=sp(15 * text_scale),
                bold=True,
                theme_text_color="Custom",
                text_color=[0.94, 0.93, 0.90, 1],
                shorten=True,
                shorten_from="right",
            )
        )
        text_col.add_widget(
            MDLabel(
                text=when,
                font_style="Body",
                font_name=FONT_REGULAR,
                font_size=sp(11 * text_scale),
                theme_text_color="Custom",
                text_color=[0.72, 0.72, 0.74, 1],
            )
        )
        if detail_text:
            text_col.add_widget(
                MDLabel(
                    text=detail_text,
                    font_style="Body",
                    font_name=FONT_REGULAR,
                    font_size=sp(10.5 * text_scale),
                    theme_text_color="Custom",
                    text_color=[0.68, 0.70, 0.72, 1],
                    shorten=True,
                    shorten_from="right",
                )
            )

        amount_label = MDLabel(
            text=f"{sign} GHS {self._format_amount(amount)}",
            size_hint_x=None,
            width=dp(124 * layout_scale),
            halign="right",
            valign="middle",
            font_name=FONT_SEMIBOLD,
            font_size=sp(15 * text_scale),
            bold=True,
            theme_text_color="Custom",
            text_color=amount_color,
        )

        row.add_widget(icon_wrap)
        row.add_widget(text_col)
        row.add_widget(amount_label)
        card.add_widget(row)
        return card

    def _render_transactions(self, transactions: list[dict]):
        container = self.ids.recent_container
        container.clear_widgets()

        if not transactions:
            empty_card = MDCard(
                size_hint_y=None,
                height=dp(70 * float(self.layout_scale or 1.0)),
                radius=[dp(18 * float(self.layout_scale or 1.0))],
                md_bg_color=TX_CARD_BG,
                line_color=[0.20, 0.23, 0.28, 0.62],
                padding=[
                    dp(14 * float(self.layout_scale or 1.0)),
                    dp(10 * float(self.layout_scale or 1.0)),
                    dp(14 * float(self.layout_scale or 1.0)),
                    dp(10 * float(self.layout_scale or 1.0)),
                ],
            )
            empty_card.add_widget(
                MDLabel(
                    text="No agent activity found yet.",
                    theme_text_color="Custom",
                    text_color=[0.72, 0.72, 0.74, 1],
                    halign="center",
                )
            )
            container.add_widget(empty_card)
            return

        for tx in transactions[:20]:
            container.add_widget(self._build_tx_card(tx))

    def load_transactions(self):
        app = MDApp.get_running_app()
        token = str(getattr(app, "access_token", "") or "").strip()
        if not token:
            self.status_text = "Sign in first to load agent activity."
            self._render_transactions([])
            return

        self.status_text = "Loading agent activity..."
        threading.Thread(target=self._load_transactions_worker, args=(token,), daemon=True).start()

    def _load_transactions_worker(self, token: str):
        headers = {"Authorization": f"Bearer {token}"}
        structure_payload = {}
        history_payload = []
        recovery_payload = []
        agent_payload = {}
        error_text = ""

        try:
            agent_resp = requests.get(f"{API_URL}/agents/me", headers=headers, timeout=12)
            agent_json = agent_resp.json() if agent_resp.content else {}
            if agent_resp.status_code < 400 and isinstance(agent_json, dict):
                agent_payload = agent_json
            elif not error_text:
                error_text = (
                    extract_backend_message(agent_json, fallback="Unable to load agent profile.")
                    if isinstance(agent_json, dict)
                    else "Unable to load agent profile."
                )
        except Exception as exc:
            if not error_text:
                error_text = sanitize_backend_message(exc, fallback="Agent profile sync unavailable.")

        try:
            summary_resp = requests.get(f"{API_URL}/agent-transactions/me/wallet-structure", headers=headers, timeout=12)
            summary_json = summary_resp.json() if summary_resp.content else {}
            if summary_resp.status_code < 400 and isinstance(summary_json, dict):
                structure_payload = summary_json
            else:
                error_text = extract_backend_message(summary_json, fallback="Unable to load wallet structure.")
        except Exception as exc:
            error_text = sanitize_backend_message(exc, fallback="Summary sync unavailable.")

        try:
            history_resp = requests.get(f"{API_URL}/agent-transactions/me/history", headers=headers, timeout=12)
            history_json = history_resp.json() if history_resp.content else []
            if history_resp.status_code < 400 and isinstance(history_json, list):
                history_payload = history_json
            elif not error_text:
                error_text = extract_backend_message(history_json, fallback="Unable to load transactions.")
        except Exception as exc:
            if not error_text:
                error_text = sanitize_backend_message(exc, fallback="History sync unavailable.")

        try:
            rec_resp = requests.get(f"{API_URL}/agent-transactions/me/recovery-candidates", headers=headers, timeout=12)
            rec_json = rec_resp.json() if rec_resp.content else []
            if rec_resp.status_code < 400 and isinstance(rec_json, list):
                recovery_payload = rec_json
        except Exception:
            recovery_payload = []

        Clock.schedule_once(
            lambda _dt: self._apply_agent_data(
                structure_payload=structure_payload,
                history_payload=history_payload,
                recovery_payload=recovery_payload,
                agent_payload=agent_payload,
                error_text=error_text,
            )
        )

    def _apply_agent_data(
        self,
        structure_payload: dict,
        history_payload: list[dict],
        recovery_payload: list[dict],
        agent_payload: dict,
        error_text: str,
    ):
        float_balance = 0.0
        commission_balance = 0.0
        if structure_payload:
            float_balance = float(structure_payload.get("agent_float_balance", 0.0) or 0.0)
            commission_balance = float(structure_payload.get("agent_commission_balance", 0.0) or 0.0)
            self.float_display = f"GHS {float_balance:,.2f}"
            self.commission_display = f"GHS {commission_balance:,.2f}"
            tx_count = int(structure_payload.get("agent_transaction_count", 0) or 0)
            self.total_transactions_label = f"{tx_count} total"
        else:
            self.float_display = "GHS 0.00"
            self.commission_display = "GHS 0.00"
            self.total_transactions_label = f"{len(history_payload)} total"

        self.agent_total_balance = float_balance + commission_balance
        self._update_balance_display()
        self.recovery_display = f"{len(recovery_payload)} item(s)"
        self._recovery_payload = list(recovery_payload or [])

        if agent_payload:
            status_raw = str(agent_payload.get("status", "unknown") or "unknown")
            status_key = status_raw.strip().lower()
            status = status_raw.replace("_", " ").title()
            commission_rate = float(agent_payload.get("commission_rate", 0.0) or 0.0) * 100.0
            agent_id = agent_payload.get("id")
            self.agent_status_display = status
            self.agent_commission_rate_display = f"{commission_rate:.1f}%"
            self.agent_commission_rate_value = float(agent_payload.get("commission_rate", 0.0) or 0.0)
            self.agent_id_display = str(agent_id) if agent_id else "--"
            self._set_status_chip(status_key)
        else:
            self.agent_status_display = "--"
            self.agent_commission_rate_display = "--"
            self.agent_commission_rate_value = 0.0
            self.agent_id_display = "--"
            self._set_status_chip("")

        self._update_greeting()

        self.funding_note = ""
        for tx in history_payload[:20]:
            if not isinstance(tx, dict):
                continue
            tx_type = str(tx.get("type", "") or "").strip().lower()
            metadata = self._extract_metadata(tx)
            if tx_type == "agent_deposit":
                fee_rate = float(metadata.get("topup_fee_rate", 0.0) or 0.0)
                if fee_rate > 0:
                    self.funding_note = f"Note: {fee_rate * 100:.0f}% top-up fee applied on recent user funding."
                    break
            if tx_type in {"agent_airtime_sale", "agent_data_bundle_sale"} and metadata.get("funding_source") == "wallet":
                self.funding_note = "Note: Wallet balance used for recent agent sale."
                break

        if history_payload:
            self.status_text = f"Last sync: {len(history_payload)} activity just now."
            self._render_transactions(history_payload)
        else:
            self.status_text = f"Last sync: {error_text}" if error_text else "Last sync: no activity yet."
            self._render_transactions([])
            if error_text:
                self._show_warning_popup(error_text)

    def show_agent_help(self):
        self._show_warning_popup(
            "Use Fund User for wallet top-ups, Sell Airtime for airtime sales, Data Bundles for live iData bundle sales, Cash Withdrawal for customer payouts, Recovery for recoverable items, and History for all activity."
        )

    def open_fund_user_dialog(self) -> None:
        content = MDBoxLayout(orientation="vertical", spacing=dp(10), size_hint_y=None)
        content.bind(minimum_height=content.setter("height"))

        def _format_money(value: float) -> str:
            return f"GHS {value:,.2f}"

        def _parse_amount(raw: str | None) -> float:
            try:
                value = float(str(raw or "").replace(",", "").strip())
            except Exception:
                return 0.0
            return value if value > 0 else 0.0

        def _make_card(title: str, lines: list[str], *, bg_color: list[float], line_color: list[float]) -> MDCard:
            card = MDCard(
                radius=[dp(18)],
                md_bg_color=bg_color,
                line_color=line_color,
                elevation=0,
                adaptive_height=True,
                padding=[dp(12)] * 4,
            )
            body = MDBoxLayout(orientation="vertical", spacing=dp(5), adaptive_height=True)
            body.add_widget(
                MDLabel(
                    text=title,
                    theme_text_color="Custom",
                    text_color=[0.95, 0.95, 0.92, 1],
                    font_size="13sp",
                    bold=True,
                    adaptive_height=True,
                )
            )
            for line in lines:
                body.add_widget(
                    MDLabel(
                        text=line,
                        theme_text_color="Custom",
                        text_color=[0.72, 0.74, 0.78, 1],
                        font_size="11sp",
                        adaptive_height=True,
                    )
                )
            card.add_widget(body)
            return card

        content.add_widget(
            MDLabel(
                text="Fund User",
                theme_text_color="Custom",
                text_color=[0.94, 0.79, 0.46, 1],
                font_size="17sp",
                bold=True,
                adaptive_height=True,
            )
        )
        content.add_widget(
            MDLabel(
                text="Top up a registered wallet with instant net credit.",
                theme_text_color="Custom",
                text_color=[0.72, 0.74, 0.78, 1],
                font_size="11.5sp",
                adaptive_height=True,
            )
        )

        content.add_widget(
            _make_card(
                "How it works",
                [
                    "1. Enter the registered phone number.",
                    "2. Enter the top-up amount in GHS.",
                    "3. The customer receives net credit after the fee.",
                ],
                bg_color=[0.10, 0.17, 0.15, 0.92],
                line_color=[0.31, 0.48, 0.41, 0.36],
            )
        )

        form_card = MDCard(
            radius=[dp(18)],
            md_bg_color=[0.09, 0.10, 0.12, 0.94],
            line_color=[0.31, 0.48, 0.41, 0.22],
            elevation=0,
            adaptive_height=True,
            padding=[dp(12)] * 4,
        )
        form_body = MDBoxLayout(orientation="vertical", spacing=dp(8), adaptive_height=True)
        form_body.add_widget(
            MDLabel(
                text="Wallet details",
                theme_text_color="Custom",
                text_color=[0.95, 0.95, 0.92, 1],
                font_size="13sp",
                bold=True,
                adaptive_height=True,
            )
        )
        form_body.add_widget(
            MDLabel(
                text="A 5% top-up fee is deducted automatically and the customer receives the balance shown in the summary.",
                theme_text_color="Custom",
                text_color=[0.72, 0.74, 0.78, 1],
                font_size="11sp",
                adaptive_height=True,
            )
        )
        form_body.add_widget(
            MDLabel(
                text="Registered phone number",
                theme_text_color="Custom",
                text_color=[0.95, 0.95, 0.92, 1],
                font_size="12sp",
                adaptive_height=True,
            )
        )
        phone_field = MDTextField(
            hint_text="0241234567",
            helper_text="Use the phone number linked to the customer wallet.",
            helper_text_mode="on_focus",
            mode="outlined",
        )
        form_body.add_widget(phone_field)
        form_body.add_widget(
            MDLabel(
                text="Top-up amount (GHS)",
                theme_text_color="Custom",
                text_color=[0.95, 0.95, 0.92, 1],
                font_size="12sp",
                adaptive_height=True,
            )
        )
        amount_field = MDTextField(
            hint_text="Amount in GHS",
            helper_text=f"A {TOPUP_FEE_RATE * 100:.0f}% fee is deducted automatically.",
            helper_text_mode="on_focus",
            mode="outlined",
            input_filter="float",
        )
        form_body.add_widget(amount_field)
        form_body.add_widget(
            MDLabel(
                text=f"Fee rate: {TOPUP_FEE_RATE * 100:.0f}% | Net credit is reflected instantly after confirmation.",
                theme_text_color="Custom",
                text_color=[0.72, 0.74, 0.78, 1],
                font_size="10.5sp",
                adaptive_height=True,
            )
        )
        form_card.add_widget(form_body)
        content.add_widget(form_card)

        summary_card = MDCard(
            radius=[dp(18)],
            md_bg_color=[0.10, 0.17, 0.15, 0.92],
            line_color=[0.93, 0.77, 0.39, 0.28],
            elevation=0,
            adaptive_height=True,
            padding=[dp(12)] * 4,
        )
        summary_body = MDBoxLayout(orientation="vertical", spacing=dp(5), adaptive_height=True)
        summary_body.add_widget(
            MDLabel(
                text="Estimated net credit",
                theme_text_color="Custom",
                text_color=[0.72, 0.74, 0.78, 1],
                font_size="11.5sp",
                adaptive_height=True,
            )
        )
        net_credit_label = MDLabel(
            text=_format_money(0.0),
            theme_text_color="Custom",
            text_color=[0.94, 0.79, 0.46, 1],
            font_size="18sp",
            bold=True,
            adaptive_height=True,
        )
        summary_body.add_widget(net_credit_label)
        detail_label = MDLabel(
            text=f"Gross amount: {_format_money(0.0)} | Fee: {_format_money(0.0)}",
            theme_text_color="Custom",
            text_color=[0.86, 0.88, 0.91, 1],
            font_size="11sp",
            adaptive_height=True,
        )
        summary_body.add_widget(detail_label)
        summary_note = MDLabel(
            text="Enter an amount to preview the fee and net credit.",
            theme_text_color="Custom",
            text_color=[0.72, 0.74, 0.78, 1],
            font_size="10.5sp",
            adaptive_height=True,
        )
        summary_body.add_widget(summary_note)
        summary_card.add_widget(summary_body)
        content.add_widget(summary_card)

        action_button = MDFillRoundFlatIconButton(
            text="Fund Wallet",
            icon="wallet-plus",
            md_bg_color=[0.93, 0.77, 0.39, 1],
            text_color=[0.07, 0.08, 0.10, 1],
            size_hint_y=None,
            height=dp(48),
        )

        def _refresh_summary(*_args) -> None:
            amount = _parse_amount(amount_field.text)
            fee = round(amount * TOPUP_FEE_RATE, 2)
            net = round(max(amount - fee, 0.0), 2)
            net_credit_label.text = _format_money(net)
            detail_label.text = f"Gross amount: {_format_money(amount)} | Fee: {_format_money(fee)}"
            summary_note.text = (
                "The customer receives the net credit instantly after confirmation."
                if amount > 0
                else "Enter an amount to preview the fee and net credit."
            )

        def _submit(*_args):
            phone = normalize_ghana_number(phone_field.text)
            if not phone or len(phone) != 10 or not phone.isdigit():
                show_message_dialog(
                    self,
                    title="Invalid Phone",
                    message="Enter the registered phone number linked to the wallet.",
                )
                return

            amount = _parse_amount(amount_field.text)
            if amount <= 0:
                show_message_dialog(self, title="Invalid Amount", message="Enter a valid top-up amount.")
                return

            fee = round(amount * TOPUP_FEE_RATE, 2)
            net = round(amount - fee, 2)
            if net <= 0:
                show_message_dialog(self, title="Invalid Amount", message="Top-up amount is too small after the fee.")
                return

            self._close_action_dialog()
            self._post_agent_action(
                "/agent-transactions/cash-deposit",
                payload={
                    "customer_phone": phone,
                    "amount": amount,
                    "currency": "GHS",
                    "topup_fee_rate": TOPUP_FEE_RATE,
                },
                success_message=f"User funded successfully. Net credit: GHS {net:.2f}. Fee: GHS {fee:.2f}.",
            )

        amount_field.bind(text=_refresh_summary)
        _refresh_summary()
        action_button.bind(on_release=_submit)
        content.add_widget(action_button)

        self._action_popup = show_custom_dialog(
            self,
            title="Fund User",
            content_cls=content,
            close_label="Close",
            auto_dismiss=True,
        )

    def open_sell_airtime_dialog(self) -> None:
        content = MDBoxLayout(orientation="vertical", spacing=dp(10), size_hint_y=None)
        content.bind(minimum_height=content.setter("height"))

        def _format_money(value: float) -> str:
            return f"GHS {value:,.2f}"

        def _parse_amount(raw: str | None) -> float:
            try:
                value = float(str(raw or "").replace(",", "").strip())
            except Exception:
                return 0.0
            return value if value > 0 else 0.0

        def _make_card(title: str, lines: list[str], *, bg_color: list[float], line_color: list[float]) -> MDCard:
            card = MDCard(
                radius=[dp(18)],
                md_bg_color=bg_color,
                line_color=line_color,
                elevation=0,
                adaptive_height=True,
                padding=[dp(12)] * 4,
            )
            body = MDBoxLayout(orientation="vertical", spacing=dp(5), adaptive_height=True)
            body.add_widget(
                MDLabel(
                    text=title,
                    theme_text_color="Custom",
                    text_color=[0.95, 0.95, 0.92, 1],
                    font_size="13sp",
                    bold=True,
                    adaptive_height=True,
                )
            )
            for line in lines:
                body.add_widget(
                    MDLabel(
                        text=line,
                        theme_text_color="Custom",
                        text_color=[0.72, 0.74, 0.78, 1],
                        font_size="11sp",
                        adaptive_height=True,
                    )
                )
            card.add_widget(body)
            return card

        commission_rate = float(self.agent_commission_rate_value or 0.0)
        commission_rate_text = str(self.agent_commission_rate_display or "").strip()
        if not commission_rate_text or commission_rate_text == "--":
            commission_rate_text = f"{commission_rate * 100:.1f}%"

        content.add_widget(
            MDLabel(
                text="Sell Airtime",
                theme_text_color="Custom",
                text_color=[0.94, 0.79, 0.46, 1],
                font_size="17sp",
                bold=True,
                adaptive_height=True,
            )
        )
        content.add_widget(
            MDLabel(
                text="Sell airtime for a registered number.",
                theme_text_color="Custom",
                text_color=[0.72, 0.74, 0.78, 1],
                font_size="11.5sp",
                adaptive_height=True,
            )
        )

        content.add_widget(
            _make_card(
                "How it works",
                [
                    "1. Enter the customer phone number.",
                    "2. Add the network and airtime amount.",
                    "3. Commission is credited after success.",
                ],
                bg_color=[0.10, 0.17, 0.15, 0.92],
                line_color=[0.31, 0.48, 0.41, 0.36],
            )
        )

        form_card = MDCard(
            radius=[dp(18)],
            md_bg_color=[0.09, 0.10, 0.12, 0.94],
            line_color=[0.31, 0.48, 0.41, 0.22],
            elevation=0,
            adaptive_height=True,
            padding=[dp(12)] * 4,
        )
        form_body = MDBoxLayout(orientation="vertical", spacing=dp(8), adaptive_height=True)
        form_body.add_widget(
            MDLabel(
                text="Sale details",
                theme_text_color="Custom",
                text_color=[0.95, 0.95, 0.92, 1],
                font_size="13sp",
                bold=True,
                adaptive_height=True,
            )
        )
        form_body.add_widget(
            MDLabel(
                text=f"Commission rate: {commission_rate_text}.",
                theme_text_color="Custom",
                text_color=[0.72, 0.74, 0.78, 1],
                font_size="11sp",
                adaptive_height=True,
            )
        )
        form_body.add_widget(
            MDLabel(
                text="Customer phone number",
                theme_text_color="Custom",
                text_color=[0.95, 0.95, 0.92, 1],
                font_size="12sp",
                adaptive_height=True,
            )
        )
        phone_field = MDTextField(
            hint_text="0241234567",
            helper_text="Use the registered customer number.",
            helper_text_mode="on_focus",
            mode="outlined",
        )
        form_body.add_widget(phone_field)
        form_body.add_widget(
            MDLabel(
                text="Network (optional)",
                theme_text_color="Custom",
                text_color=[0.95, 0.95, 0.92, 1],
                font_size="12sp",
                adaptive_height=True,
            )
        )
        network_field = MDTextField(
            hint_text="MTN, Telecel, or AirtelTigo",
            helper_text="Leave blank to auto-detect from the number.",
            helper_text_mode="on_focus",
            mode="outlined",
        )
        form_body.add_widget(network_field)
        form_body.add_widget(
            MDLabel(
                text="Airtime amount (GHS)",
                theme_text_color="Custom",
                text_color=[0.95, 0.95, 0.92, 1],
                font_size="12sp",
                adaptive_height=True,
            )
        )
        amount_field = MDTextField(
            hint_text="Amount in GHS",
            helper_text="Enter the airtime value to sell.",
            helper_text_mode="on_focus",
            mode="outlined",
            input_filter="float",
        )
        form_body.add_widget(amount_field)
        form_body.add_widget(
            MDLabel(
                text="Commission is reflected instantly after success.",
                theme_text_color="Custom",
                text_color=[0.72, 0.74, 0.78, 1],
                font_size="10.5sp",
                adaptive_height=True,
            )
        )
        form_card.add_widget(form_body)
        content.add_widget(form_card)

        summary_card = MDCard(
            radius=[dp(18)],
            md_bg_color=[0.10, 0.17, 0.15, 0.92],
            line_color=[0.93, 0.77, 0.39, 0.28],
            elevation=0,
            adaptive_height=True,
            padding=[dp(12)] * 4,
        )
        summary_body = MDBoxLayout(orientation="vertical", spacing=dp(5), adaptive_height=True)
        summary_body.add_widget(
            MDLabel(
                text="Commission preview",
                theme_text_color="Custom",
                text_color=[0.72, 0.74, 0.78, 1],
                font_size="11.5sp",
                adaptive_height=True,
            )
        )
        commission_label = MDLabel(
            text=_format_money(0.0),
            theme_text_color="Custom",
            text_color=[0.94, 0.79, 0.46, 1],
            font_size="18sp",
            bold=True,
            adaptive_height=True,
        )
        summary_body.add_widget(commission_label)
        detail_label = MDLabel(
            text=f"Sale amount: {_format_money(0.0)} | Commission: {_format_money(0.0)}",
            theme_text_color="Custom",
            text_color=[0.86, 0.88, 0.91, 1],
            font_size="11sp",
            adaptive_height=True,
        )
        summary_body.add_widget(detail_label)
        summary_note = MDLabel(
            text="Enter an amount to preview the commission.",
            theme_text_color="Custom",
            text_color=[0.72, 0.74, 0.78, 1],
            font_size="10.5sp",
            adaptive_height=True,
        )
        summary_body.add_widget(summary_note)
        summary_card.add_widget(summary_body)
        content.add_widget(summary_card)

        action_button = MDFillRoundFlatIconButton(
            text="Sell Airtime",
            icon="phone-forward",
            md_bg_color=[0.93, 0.77, 0.39, 1],
            text_color=[0.07, 0.08, 0.10, 1],
            size_hint_y=None,
            height=dp(48),
        )

        def _refresh_summary(*_args) -> None:
            amount = _parse_amount(amount_field.text)
            commission = round(amount * commission_rate, 2)
            commission_label.text = _format_money(commission)
            detail_label.text = f"Sale amount: {_format_money(amount)} | Commission: {_format_money(commission)}"
            summary_note.text = (
                "Airtime is sold instantly after confirmation."
                if amount > 0
                else "Enter an amount to preview the commission."
            )

        def _submit(*_args):
            phone = normalize_ghana_number(phone_field.text)
            if not phone or len(phone) != 10 or not phone.isdigit():
                show_message_dialog(
                    self,
                    title="Invalid Phone",
                    message="Enter the registered phone number linked to the customer.",
                )
                return

            amount = _parse_amount(amount_field.text)
            if amount <= 0:
                show_message_dialog(self, title="Invalid Amount", message="Enter a valid airtime amount.")
                return

            network = self._normalize_network_label(network_field.text)
            if not network:
                network = self._normalize_network_label(detect_network(phone))
            if not network or network == "UNKNOWN":
                show_message_dialog(self, title="Network Needed", message="Choose a valid network.")
                return

            commission = round(amount * commission_rate, 2)
            self._close_action_dialog()
            self._post_agent_action(
                "/agents/me/sell-airtime",
                payload={
                    "phone_number": phone,
                    "amount": amount,
                    "currency": "GHS",
                    "network_provider": network,
                },
                success_message=f"Airtime sale submitted. Commission: GHS {commission:.2f}.",
            )

        amount_field.bind(text=_refresh_summary)
        _refresh_summary()
        action_button.bind(on_release=_submit)
        content.add_widget(action_button)

        self._action_popup = show_custom_dialog(
            self,
            title="Sell Airtime",
            content_cls=content,
            close_label="Close",
            auto_dismiss=True,
        )

    def open_data_bundle_dialog(self) -> None:
        app = MDApp.get_running_app()
        manager = self.manager or getattr(app, "root", None)
        if not manager or not manager.has_screen("data_bundle"):
            show_message_dialog(
                self,
                title="Data Bundles",
                message="The data bundle screen is not available right now.",
                close_label="Close",
            )
            return

        data_bundle_screen = manager.get_screen("data_bundle")
        if hasattr(data_bundle_screen, "configure_agent_mode"):
            data_bundle_screen.configure_agent_mode()
        manager.current = "data_bundle"

    def open_cash_withdraw_dialog(self) -> None:
        content = MDBoxLayout(orientation="vertical", spacing=dp(10), size_hint_y=None)
        content.bind(minimum_height=content.setter("height"))

        def _format_money(value: float) -> str:
            return f"GHS {value:,.2f}"

        def _parse_amount(raw: str | None) -> float:
            try:
                value = float(str(raw or "").replace(",", "").strip())
            except Exception:
                return 0.0
            return value if value > 0 else 0.0

        def _make_card(title: str, lines: list[str], *, bg_color: list[float], line_color: list[float]) -> MDCard:
            card = MDCard(
                radius=[dp(18)],
                md_bg_color=bg_color,
                line_color=line_color,
                elevation=0,
                adaptive_height=True,
                padding=[dp(12)] * 4,
            )
            body = MDBoxLayout(orientation="vertical", spacing=dp(5), adaptive_height=True)
            body.add_widget(
                MDLabel(
                    text=title,
                    theme_text_color="Custom",
                    text_color=[0.95, 0.95, 0.92, 1],
                    font_size="13sp",
                    bold=True,
                    adaptive_height=True,
                )
            )
            for line in lines:
                body.add_widget(
                    MDLabel(
                        text=line,
                        theme_text_color="Custom",
                        text_color=[0.72, 0.74, 0.78, 1],
                        font_size="11sp",
                        adaptive_height=True,
                    )
                )
            card.add_widget(body)
            return card

        content.add_widget(
            MDLabel(
                text="Cash Withdrawal",
                theme_text_color="Custom",
                text_color=[0.94, 0.79, 0.46, 1],
                font_size="17sp",
                bold=True,
                adaptive_height=True,
            )
        )
        content.add_widget(
            MDLabel(
                text="Withdraw cash for a registered customer with clean debit details.",
                theme_text_color="Custom",
                text_color=[0.72, 0.74, 0.78, 1],
                font_size="11.5sp",
                adaptive_height=True,
            )
        )

        content.add_widget(
            _make_card(
                "How it works",
                [
                    "1. Enter the registered phone number.",
                    "2. Enter the cash-out amount in GHS.",
                    "3. The wallet is debited and the payout is processed.",
                ],
                bg_color=[0.10, 0.16, 0.14, 0.92],
                line_color=[0.53, 0.41, 0.23, 0.34],
            )
        )

        form_card = MDCard(
            radius=[dp(18)],
            md_bg_color=[0.09, 0.10, 0.12, 0.94],
            line_color=[0.53, 0.41, 0.23, 0.22],
            elevation=0,
            adaptive_height=True,
            padding=[dp(12)] * 4,
        )
        form_body = MDBoxLayout(orientation="vertical", spacing=dp(8), adaptive_height=True)
        form_body.add_widget(
            MDLabel(
                text="Payout details",
                theme_text_color="Custom",
                text_color=[0.95, 0.95, 0.92, 1],
                font_size="13sp",
                bold=True,
                adaptive_height=True,
            )
        )
        form_body.add_widget(
            MDLabel(
                text=f"A {WITHDRAWAL_FEE_RATE * 100:.0f}% withdrawal fee is added automatically and charged to the wallet.",
                theme_text_color="Custom",
                text_color=[0.72, 0.74, 0.78, 1],
                font_size="11sp",
                adaptive_height=True,
            )
        )
        form_body.add_widget(
            MDLabel(
                text="Registered phone number",
                theme_text_color="Custom",
                text_color=[0.95, 0.95, 0.92, 1],
                font_size="12sp",
                adaptive_height=True,
            )
        )
        customer_phone_field = MDTextField(
            hint_text="0241234567",
            helper_text="Use the phone number linked to the customer wallet.",
            helper_text_mode="on_focus",
            mode="outlined",
        )
        form_body.add_widget(customer_phone_field)
        form_body.add_widget(
            MDLabel(
                text="Cash-out amount (GHS)",
                theme_text_color="Custom",
                text_color=[0.95, 0.95, 0.92, 1],
                font_size="12sp",
                adaptive_height=True,
            )
        )
        amount_field = MDTextField(
            hint_text="Amount in GHS",
            helper_text=f"A {WITHDRAWAL_FEE_RATE * 100:.0f}% fee is added automatically.",
            helper_text_mode="on_focus",
            mode="outlined",
            input_filter="float",
        )
        form_body.add_widget(amount_field)
        form_body.add_widget(
            MDLabel(
                text=f"Fee rate: {WITHDRAWAL_FEE_RATE * 100:.0f}% | Customer receives the cash-out amount shown in the summary.",
                theme_text_color="Custom",
                text_color=[0.72, 0.74, 0.78, 1],
                font_size="10.5sp",
                adaptive_height=True,
            )
        )
        form_card.add_widget(form_body)
        content.add_widget(form_card)

        summary_card = MDCard(
            radius=[dp(18)],
            md_bg_color=[0.16, 0.14, 0.10, 0.92],
            line_color=[0.93, 0.77, 0.39, 0.28],
            elevation=0,
            adaptive_height=True,
            padding=[dp(12)] * 4,
        )
        summary_body = MDBoxLayout(orientation="vertical", spacing=dp(5), adaptive_height=True)
        summary_body.add_widget(
            MDLabel(
                text="Estimated wallet debit",
                theme_text_color="Custom",
                text_color=[0.72, 0.74, 0.78, 1],
                font_size="11.5sp",
                adaptive_height=True,
            )
        )
        debit_label = MDLabel(
            text=_format_money(0.0),
            theme_text_color="Custom",
            text_color=[0.94, 0.79, 0.46, 1],
            font_size="18sp",
            bold=True,
            adaptive_height=True,
        )
        summary_body.add_widget(debit_label)
        detail_label = MDLabel(
            text=f"Cash-out amount: {_format_money(0.0)} | Fee: {_format_money(0.0)}",
            theme_text_color="Custom",
            text_color=[0.86, 0.88, 0.91, 1],
            font_size="11sp",
            adaptive_height=True,
        )
        summary_body.add_widget(detail_label)
        summary_note = MDLabel(
            text="Enter an amount to preview the total debit.",
            theme_text_color="Custom",
            text_color=[0.72, 0.74, 0.78, 1],
            font_size="10.5sp",
            adaptive_height=True,
        )
        summary_body.add_widget(summary_note)
        summary_card.add_widget(summary_body)
        content.add_widget(summary_card)

        action_button = MDFillRoundFlatIconButton(
            text="Confirm Withdrawal",
            icon="cash-fast",
            md_bg_color=[0.93, 0.77, 0.39, 1],
            text_color=[0.07, 0.08, 0.10, 1],
            size_hint_y=None,
            height=dp(48),
        )

        def _refresh_summary(*_args) -> None:
            amount = _parse_amount(amount_field.text)
            fee = round(amount * WITHDRAWAL_FEE_RATE, 2)
            total_debit = round(amount + fee, 2)
            debit_label.text = _format_money(total_debit)
            detail_label.text = f"Cash-out amount: {_format_money(amount)} | Fee: {_format_money(fee)}"
            summary_note.text = (
                "The customer receives the cash-out amount; the wallet is debited with the fee included."
                if amount > 0
                else "Enter an amount to preview the total debit."
            )

        def _submit(*_args):
            customer_phone = normalize_ghana_number(customer_phone_field.text)
            if not customer_phone or len(customer_phone) != 10 or not customer_phone.isdigit():
                show_message_dialog(
                    self,
                    title="Invalid Phone",
                    message="Enter the registered phone number linked to the wallet.",
                )
                return

            amount = _parse_amount(amount_field.text)
            if amount <= 0:
                show_message_dialog(self, title="Invalid Amount", message="Enter a valid withdrawal amount.")
                return

            fee = round(amount * WITHDRAWAL_FEE_RATE, 2)
            total_debit = round(amount + fee, 2)

            self._close_action_dialog()
            self._post_agent_action(
                "/agent-transactions/cash-withdrawal",
                payload={
                    "customer_phone": customer_phone,
                    "amount": amount,
                    "currency": "GHS",
                },
                success_message=(
                    f"Cash withdrawal submitted successfully. Fee: GHS {fee:.2f}. Total debit: GHS {total_debit:.2f}."
                ),
            )

        amount_field.bind(text=_refresh_summary)
        _refresh_summary()
        action_button.bind(on_release=_submit)
        content.add_widget(action_button)

        self._action_popup = show_custom_dialog(
            self,
            title="Cash Withdrawal",
            content_cls=content,
            close_label="Close",
            auto_dismiss=True,
        )

    def go_back(self):
        if not self.manager:
            return
        previous = str(getattr(self.manager, "previous_screen", "") or "").strip()
        if previous and previous != self.name and previous != "splash" and self.manager.has_screen(previous):
            self.manager.current = previous
            return
        self.manager.current = "home"


Builder.load_string(KV)
