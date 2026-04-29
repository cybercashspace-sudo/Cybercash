import json
import threading
import time
from datetime import datetime, timezone

import requests
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.metrics import dp, sp
from kivy.properties import BooleanProperty, NumericProperty, StringProperty
from kivy.uix.gridlayout import GridLayout
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDButton, MDButtonText, MDIconButton
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivymd.uix.screen import MDScreen

from api.client import API_URL
from core.bottom_nav import BottomNavBar
from core.message_sanitizer import extract_backend_message, sanitize_backend_message
from core.paystack_checkout import open_paystack_checkout, warmup_paystack_checkout
from core.popup_manager import show_confirm_dialog, show_custom_dialog, show_message_dialog

AGENT_REGISTRATION_FEE_GHS = 100.0
AGENT_STARTUP_LOAN_GHS = 50.0
AGENT_VERIFY_POLL_INTERVAL_SECONDS = 3
AGENT_VERIFY_MAX_POLLS = 40
FONT_REGULAR = "kivy_frontend/assets/fonts/Inter-Regular.ttf"
FONT_SEMIBOLD = "kivy_frontend/assets/fonts/Inter-SemiBold.ttf"
FONT_BOLD = "kivy_frontend/assets/fonts/Inter-Bold.ttf"
TX_CARD_BG = [0.09, 0.10, 0.12, 0.88]
TX_ICON_BG = [0.18, 0.24, 0.20, 0.96]
POSITIVE_COLOR = [0.61, 0.88, 0.72, 1]
NEGATIVE_COLOR = [0.98, 0.48, 0.41, 1]

KV = """
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
#:import sp kivy.metrics.sp
<DashboardScreen>:
    MDBoxLayout:
        orientation: "vertical"

        canvas.before:
            Color:
                rgba: app.ui_background
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
                rgba: app.ui_overlay
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

                        MDIconButton:
                            icon: "account-circle"
                            user_font_size: str(30 * root.icon_scale) + "sp"
                            size_hint: None, None
                            size: dp(30 * root.layout_scale), dp(30 * root.layout_scale)
                            pos_hint: {"center_x": 0.5, "center_y": 0.5}
                            theme_text_color: "Custom"
                            text_color: app.gold
                            on_release: root.go_to_settings()

                    MDLabel:
                        text: "CYBER CASH"
                        halign: "center"
                        bold: True
                        font_style: "Title"
                        font_name: FONT_BOLD
                        font_size: sp(24 * root.text_scale)
                        theme_text_color: "Custom"
                        text_color: app.gold

                    FloatLayout:
                        size_hint: None, None
                        size: dp(44 * root.layout_scale), dp(54 * root.layout_scale)

                        MDIconButton:
                            icon: "bell-ring-outline"
                            user_font_size: str(24 * root.icon_scale) + "sp"
                            size_hint: None, None
                            size: dp(24 * root.layout_scale), dp(24 * root.layout_scale)
                            pos_hint: {"center_x": 0.5, "center_y": 0.58}
                            theme_text_color: "Custom"
                            text_color: app.gold
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
                    md_bg_color: app.ui_surface
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

                            MDIconButton:
                                icon: "card-account-details-outline"
                                user_font_size: str(18 * root.icon_scale) + "sp"
                                size_hint: None, None
                                size: dp(22 * root.layout_scale), dp(22 * root.layout_scale)
                                pos_hint: {"center_x": 0.5, "center_y": 0.5}
                                theme_text_color: "Custom"
                                text_color: 0.94, 0.78, 0.44, 1
                                disabled: True

                        MDLabel:
                            text: root.greeting_text
                            font_style: "Body"
                            font_name: FONT_SEMI
                            font_size: sp(16 * root.text_scale)
                            theme_text_color: "Custom"
                            text_color: app.ui_text_primary
                            shorten: True
                            shorten_from: "right"

                MDCard:
                    radius: [dp(22 * root.layout_scale)]
                    md_bg_color: app.ui_glass
                    line_color: [0.44, 0.63, 0.54, 0.50]
                    elevation: 0
                    padding: [dp(16 * root.layout_scale), dp(16 * root.layout_scale), dp(16 * root.layout_scale), dp(16 * root.layout_scale)]
                    size_hint_y: None
                    height: dp(178 * root.layout_scale)

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
                        spacing: dp(8 * root.layout_scale)

                        MDBoxLayout:
                            size_hint_y: None
                            height: dp(42 * root.layout_scale)
                            spacing: dp(10 * root.layout_scale)

                            MDCard:
                                size_hint: None, None
                                size: dp(34 * root.layout_scale), dp(34 * root.layout_scale)
                                radius: [dp(11 * root.layout_scale)]
                                md_bg_color: 0.44, 0.66, 0.34, 0.92
                                pos_hint: {"center_y": 0.5}
                                padding: dp(6 * root.layout_scale)
                                elevation: 0

                                MDIconButton:
                                    icon: "wallet-outline"
                                    user_font_size: str(18 * root.icon_scale) + "sp"
                                    size_hint: None, None
                                    size: dp(22 * root.layout_scale), dp(22 * root.layout_scale)
                                    pos_hint: {"center_x": 0.5, "center_y": 0.5}
                                    theme_text_color: "Custom"
                                    text_color: 0.91, 0.98, 0.83, 1
                                    halign: "center"
                                    valign: "middle"
                                    text_size: self.size
                                    disabled: True

                            MDLabel:
                                text: "Wallet Balance"
                                bold: True
                                font_style: "Body"
                                font_name: FONT_SEMI
                                font_size: sp(15 * root.text_scale)
                                theme_text_color: "Custom"
                                text_color: app.ui_text_primary
                                valign: "middle"

                            MDCard:
                                size_hint: None, None
                                size: dp(34 * root.layout_scale), dp(34 * root.layout_scale)
                                radius: [dp(17 * root.layout_scale)]
                                md_bg_color: 0.12, 0.22, 0.19, 0.62
                                line_color: [0.55, 0.73, 0.62, 0.22]
                                pos_hint: {"center_y": 0.5}
                                padding: dp(5 * root.layout_scale)
                                elevation: 0

                                MDIconButton:
                                    icon: "eye-off-outline" if root.balance_hidden else "eye-outline"
                                    user_font_size: str(18 * root.icon_scale) + "sp"
                                    size_hint: None, None
                                    size: dp(24 * root.layout_scale), dp(24 * root.layout_scale)
                                    halign: "center"
                                    valign: "middle"
                                    text_size: self.size
                                    pos_hint: {"center_x": 0.5, "center_y": 0.5}
                                    theme_text_color: "Custom"
                                    text_color: 0.90, 0.96, 0.84, 1
                                    on_release: root.toggle_balance()

                        MDLabel:
                            text: root.balance_display
                            bold: True
                            font_style: "Headline"
                            font_name: FONT_BOLD
                            font_size: sp(37 * root.text_scale)
                            theme_text_color: "Custom"
                            text_color: app.gold

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
                        on_release: root.go_to_deposit()
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

                                MDIconButton:
                                    icon: "plus"
                                    user_font_size: str(20 * root.icon_scale) + "sp"
                                    size_hint: None, None
                                    size: dp(22 * root.layout_scale), dp(22 * root.layout_scale)
                                    pos_hint: {"center_x": 0.5, "center_y": 0.5}
                                    theme_text_color: "Custom"
                                    text_color: 0.23, 0.17, 0.08, 1
                                    disabled: True

                            MDLabel:
                                text: "Deposit"
                                bold: True
                                valign: "middle"
                                font_style: "Title"
                                font_name: FONT_BOLD
                                font_size: sp(16 * root.text_scale)
                                theme_text_color: "Custom"
                                text_color: 0, 0, 0, 1

                    MDCard:
                        radius: [dp(20 * root.layout_scale)]
                        md_bg_color: app.emerald
                        line_color: [0.59, 0.79, 0.66, 0.54]
                        elevation: 0
                        padding: [dp(10 * root.layout_scale), dp(8 * root.layout_scale), dp(14 * root.layout_scale), dp(8 * root.layout_scale)]
                        on_release: root.go_to_withdraw()
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

                                MDIconButton:
                                    icon: "cash-minus"
                                    user_font_size: str(20 * root.icon_scale) + "sp"
                                    size_hint: None, None
                                    size: dp(22 * root.layout_scale), dp(22 * root.layout_scale)
                                    pos_hint: {"center_x": 0.5, "center_y": 0.5}
                                    theme_text_color: "Custom"
                                    text_color: 0.78, 0.93, 0.77, 1
                                    disabled: True

                            MDBoxLayout:
                                orientation: "vertical"
                                spacing: dp(1 * root.layout_scale)

                                Widget:

                                MDLabel:
                                    text: "Withdraw"
                                    bold: True
                                    font_style: "Title"
                                    font_name: FONT_BOLD
                                    font_size: sp(16 * root.text_scale)
                                    theme_text_color: "Custom"
                                    text_color: app.ui_text_primary
                                    adaptive_height: True

                                MDLabel:
                                    text: "To agent • 1% fee"
                                    theme_text_color: "Custom"
                                    text_color: 0.78, 0.93, 0.77, 1
                                    font_name: FONT_SEMI
                                    font_size: sp(11.5 * root.text_scale)
                                    adaptive_height: True

                                Widget:

                MDBoxLayout:
                    adaptive_height: True

                    MDLabel:
                        text: "Quick Actions"
                        font_style: "Title"
                        font_name: FONT_BOLD
                        font_size: sp(20 * root.text_scale)
                        theme_text_color: "Custom"
                        text_color: app.gold

                    MDTextButton:
                        text: "View All >"
                        theme_text_color: "Custom"
                        text_color: app.gold
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
                        md_bg_color: app.ui_surface_soft
                        line_color: [0.31, 0.48, 0.41, 0.42]
                        elevation: 0
                        padding: [dp(4 * root.layout_scale), dp(4 * root.layout_scale), dp(4 * root.layout_scale), dp(4 * root.layout_scale)]
                        MDBoxLayout:
                            orientation: "vertical"
                            spacing: "0dp"
                            MDIconButton:
                                icon: "send"
                                user_font_size: str(30 * root.icon_scale) + "sp"
                                size_hint: None, None
                                size: dp(30 * root.layout_scale), dp(30 * root.layout_scale)
                                pos_hint: {"center_x": 0.5, "center_y": 0.5}
                                theme_text_color: "Custom"
                                text_color: 0.55, 0.84, 0.66, 1
                                on_release: root.go_to_p2p_transfer()
                            MDLabel:
                                text: "Send"
                                halign: "center"
                                font_name: FONT_SEMI
                                font_size: sp(12 * root.text_scale)
                                theme_text_color: "Custom"
                                text_color: app.ui_text_primary

                    MDCard:
                        radius: [dp(16 * root.layout_scale)]
                        md_bg_color: app.ui_surface_soft
                        line_color: [0.35, 0.50, 0.41, 0.42]
                        elevation: 0
                        padding: [dp(4 * root.layout_scale), dp(4 * root.layout_scale), dp(4 * root.layout_scale), dp(4 * root.layout_scale)]
                        MDBoxLayout:
                            orientation: "vertical"
                            spacing: "0dp"
                            MDIconButton:
                                icon: "finance"
                                user_font_size: str(30 * root.icon_scale) + "sp"
                                size_hint: None, None
                                size: dp(30 * root.layout_scale), dp(30 * root.layout_scale)
                                pos_hint: {"center_x": 0.5, "center_y": 0.5}
                                theme_text_color: "Custom"
                                text_color: 0.91, 0.75, 0.44, 1
                                on_release: root.go_to_investments()
                            MDLabel:
                                text: "Invest"
                                halign: "center"
                                font_name: FONT_SEMI
                                font_size: sp(12 * root.text_scale)
                                theme_text_color: "Custom"
                                text_color: app.ui_text_primary

                    MDCard:
                        radius: [dp(16 * root.layout_scale)]
                        md_bg_color: app.ui_surface_soft
                        line_color: [0.34, 0.48, 0.40, 0.38]
                        elevation: 0
                        padding: [dp(4 * root.layout_scale), dp(4 * root.layout_scale), dp(4 * root.layout_scale), dp(4 * root.layout_scale)]
                        MDBoxLayout:
                            orientation: "vertical"
                            spacing: "0dp"
                            MDIconButton:
                                icon: "shield-check-outline"
                                user_font_size: str(30 * root.icon_scale) + "sp"
                                size_hint: None, None
                                size: dp(30 * root.layout_scale), dp(30 * root.layout_scale)
                                pos_hint: {"center_x": 0.5, "center_y": 0.5}
                                theme_text_color: "Custom"
                                text_color: 0.83, 0.92, 0.60, 1
                                on_release: root.go_to_loans()
                            MDLabel:
                                text: "Loan"
                                halign: "center"
                                font_name: FONT_SEMI
                                font_size: sp(12 * root.text_scale)
                                theme_text_color: "Custom"
                                text_color: app.ui_text_primary

                    MDCard:
                        radius: [dp(16 * root.layout_scale)]
                        md_bg_color: app.ui_surface_soft
                        line_color: [0.53, 0.41, 0.23, 0.40]
                        elevation: 0
                        on_release: root.open_more_actions()
                        padding: [dp(4 * root.layout_scale), dp(4 * root.layout_scale), dp(4 * root.layout_scale), dp(4 * root.layout_scale)]
                        MDBoxLayout:
                            orientation: "vertical"
                            spacing: "0dp"
                            MDIconButton:
                                icon: "view-grid"
                                user_font_size: str(30 * root.icon_scale) + "sp"
                                size_hint: None, None
                                size: dp(30 * root.layout_scale), dp(30 * root.layout_scale)
                                pos_hint: {"center_x": 0.5, "center_y": 0.5}
                                theme_text_color: "Custom"
                                text_color: 0.90, 0.75, 0.43, 1
                                on_release: root.open_more_actions()
                            MDLabel:
                                text: "More"
                                halign: "center"
                                font_name: FONT_SEMI
                                font_size: sp(12 * root.text_scale)
                                theme_text_color: "Custom"
                                text_color: app.ui_text_primary

                MDBoxLayout:
                    adaptive_height: True

                    MDLabel:
                        text: "Recent Activity"
                        font_style: "Title"
                        font_name: FONT_BOLD
                        font_size: sp(20 * root.text_scale)
                        theme_text_color: "Custom"
                        text_color: app.ui_text_primary

                    MDTextButton:
                        text: "View All >"
                        theme_text_color: "Custom"
                        text_color: app.gold
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
            nav_variant: "default"
            active_target: "home"
            layout_scale: root.layout_scale
            text_scale: root.text_scale
            icon_scale: root.icon_scale
            bar_color: app.ui_surface
            active_color: app.gold
            inactive_color: app.ui_text_secondary
"""


class DashboardScreen(MDScreen):
    layout_scale = NumericProperty(1.0)
    text_scale = NumericProperty(1.0)
    icon_scale = NumericProperty(1.0)
    quick_action_cols = NumericProperty(4)
    greeting_text = StringProperty("Hello, John")
    dashboard_status = StringProperty("Loading balance...")
    agent_quick_label = StringProperty("Become Agent")
    wallet_balance = NumericProperty(0.0)
    balance_hidden = BooleanProperty(False)
    balance_display = StringProperty("GHS 0.00")
    is_agent_valid = BooleanProperty(False)
    _refresh_event = None
    _is_loading = False
    _last_warning_popup = ""
    _more_actions_dialog = None
    _agent_verify_sequence = 0
    _last_agent_reference = ""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        Window.bind(size=self._on_window_resize)
        self._refresh_responsive_metrics()

    def on_pre_enter(self):
        self._refresh_responsive_metrics()
        self.load_dashboard_data()

    def on_enter(self):
        if not self._refresh_event:
            self._refresh_event = Clock.schedule_interval(lambda _dt: self.load_dashboard_data(), 25)

    def on_leave(self):
        if self._refresh_event:
            self._refresh_event.cancel()
            self._refresh_event = None
        self._agent_verify_sequence += 1
        self._close_more_actions_dialog()

    def toggle_balance(self):
        self.balance_hidden = not self.balance_hidden
        self._update_balance_display()

    @staticmethod
    def _clamp(value: float, minimum: float, maximum: float) -> float:
        return max(minimum, min(maximum, float(value)))

    def _on_window_resize(self, *_args):
        self._refresh_responsive_metrics()

    def _refresh_responsive_metrics(self):
        width, height = Window.size
        base_width = 390.0
        base_height = 844.0
        width_ratio = float(width or base_width) / base_width
        height_ratio = float(height or base_height) / base_height
        compact_penalty = 0.94 if width < 360 else 1.0
        layout = self._clamp((width_ratio * 0.68 + height_ratio * 0.32) * compact_penalty, 0.78, 1.12)
        text = self._clamp(layout * (0.98 if width < 360 else 1.0), 0.86, 1.08)
        icon = self._clamp(layout * 1.02, 0.88, 1.10)

        self.layout_scale = layout
        self.text_scale = text
        self.icon_scale = icon
        self.quick_action_cols = 4 if width >= 360 else 2

    def _update_balance_display(self):
        if self.balance_hidden:
            self.balance_display = "GHS ****.**"
        else:
            self.balance_display = f"GHS {float(self.wallet_balance or 0.0):,.2f}"

    @staticmethod
    def _format_amount(amount: float) -> str:
        value = float(amount or 0.0)
        if abs(value - int(value)) < 1e-9:
            return f"{int(value):,}"
        return f"{value:,.2f}"

    @staticmethod
    def _format_currency(value: object) -> str:
        try:
            amount = float(value or 0.0)
        except Exception:
            amount = 0.0
        return f"{amount:,.2f}"

    @staticmethod
    def _safe_first_name(value: str) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        first = raw.split()[0].strip()
        if not first or first.isdigit():
            return ""
        return first[:24]

    def _set_greeting(self, name: str = "") -> None:
        first_name = self._safe_first_name(name)
        self.greeting_text = f"Hello, {first_name}" if first_name else "Hello, John"

    @staticmethod
    def _friendly_sync_message(raw_message: str, fallback: str) -> str:
        text = str(raw_message or "").strip()
        if not text:
            return fallback

        lower = text.lower()
        if (
            "unable to connect to the remote server" in lower
            or "connection refused" in lower
            or "wallet sync unavailable" in lower
        ):
            return "Connection issue. Check internet and try again."
        if "timed out" in lower or "timeout" in lower:
            return "Request took too long. Please try again."
        if "unauthorized" in lower or "forbidden" in lower:
            return "Session expired. Please sign in again."
        if "too many attempts" in lower:
            return "Too many requests. Please wait a moment and try again."
        if "unable to load wallet balance" in lower:
            return "Unable to load wallet balance right now."
        if "unable to load activity" in lower or "activity sync unavailable" in lower:
            return "Unable to load activity right now."
        return text

    def _extract_detail(self, payload: object) -> str:
        return extract_backend_message(payload)

    def _show_warning_popup(self, message: str):
        msg = str(message or "").strip()
        if not msg or msg == self._last_warning_popup:
            return
        self._last_warning_popup = msg
        show_message_dialog(
            self,
            title="Sync Notice",
            message=msg,
            close_label="Close",
        )

    @staticmethod
    def _parse_metadata(tx: dict) -> dict:
        raw_metadata = tx.get("metadata_json")
        if isinstance(raw_metadata, dict):
            return raw_metadata
        if isinstance(raw_metadata, str) and raw_metadata.strip():
            try:
                parsed = json.loads(raw_metadata)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                return {}
        return {}

    def _friendly_title(self, tx: dict) -> str:
        tx_type = str(tx.get("type", "") or "").strip().lower()
        metadata = self._parse_metadata(tx)

        if tx_type == "transfer":
            transfer_kind = str(metadata.get("transfer_kind", "") or "").strip().lower()
            direction = str(metadata.get("direction", "")).lower()
            if transfer_kind == "withdraw_to_agent":
                return "Agent Withdrawal Received" if direction == "receive" else "Withdraw To Agent"
            if transfer_kind == "wallet_transfer":
                return "P2P Received" if direction == "receive" else "P2P Transfer"
            return "Transfer Received" if direction == "receive" else "Funds Transfer"

        mapping = {
            "agent_deposit": "Deposit from Agent",
            "agent_withdrawal": "Agent Withdrawal",
            "funding": "Paystack Deposit",
            "airtime": "Airtime Purchase",
            "data": "Data Bundle Purchase",
            "loan_disburse": "Loan Disbursement",
            "investment_create": "Investment Deposit",
            "investment_payout": "Investment Payout",
        }
        if tx_type in mapping:
            return mapping[tx_type]
        return tx_type.replace("_", " ").title() if tx_type else "Transaction"

    def _transfer_breakdown_text(self, tx: dict) -> str:
        tx_type = str(tx.get("type", "") or "").strip().lower()
        if tx_type != "transfer":
            return ""

        metadata = self._parse_metadata(tx)
        transfer_kind = str(metadata.get("transfer_kind", "") or "").strip().lower()
        direction = str(metadata.get("direction", "") or "").strip().lower()
        if transfer_kind not in {"withdraw_to_agent", "wallet_transfer"} or direction != "send":
            return ""

        transferred_amount = metadata.get("transferred_amount", 0.0)
        transfer_fee = metadata.get("transfer_fee", 0.0)
        transfer_fee_rate = float(metadata.get("transfer_fee_rate", 0.0) or 0.0)
        total_debited = metadata.get("total_debited", tx.get("amount", 0.0))
        fee_label = f"Fee ({transfer_fee_rate * 100:.1f}%)" if transfer_fee_rate > 0 else "Fee"
        if transfer_kind == "wallet_transfer" and transfer_fee_rate > 0:
            try:
                feeable_amount = float(metadata.get("p2p_feeable_amount", 0.0) or 0.0)
            except Exception:
                feeable_amount = 0.0
            if feeable_amount > 0:
                fee_label = f"Fee ({transfer_fee_rate * 100:.1f}% on GHS {self._format_currency(feeable_amount)})"
            elif float(transfer_fee or 0.0) <= 0:
                fee_label = "Fee (free today)"
        return (
            f"Amt GHS {self._format_currency(transferred_amount)} | "
            f"{fee_label} GHS {self._format_currency(transfer_fee)} | "
            f"Total GHS {self._format_currency(total_debited)}"
        )

    def _friendly_time(self, timestamp: str) -> str:
        raw = str(timestamp or "").strip()
        if not raw:
            return "Today"
        try:
            dt_value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            tx_day = dt_value.astimezone(timezone.utc).date()
            if tx_day == now.date():
                return "Today"
            if (now.date() - tx_day).days == 1:
                return "Yesterday"
            return dt_value.strftime("%d %b")
        except Exception:
            return "Recent"

    def _friendly_icon(self, tx: dict) -> tuple[str, list[float]]:
        amount = float(tx.get("amount", 0.0) or 0.0)
        positive = amount >= 0
        icon = "arrow-top-right" if positive else "arrow-bottom-right"
        color = POSITIVE_COLOR if positive else NEGATIVE_COLOR
        return icon, color

    def _build_recent_item(self, tx: dict) -> MDCard:
        app = MDApp.get_running_app()
        amount = float(tx.get("amount", 0.0) or 0.0)
        positive = amount >= 0
        sign = "+" if positive else "-"
        icon_name, icon_color = self._friendly_icon(tx)
        detail_text = self._transfer_breakdown_text(tx)
        layout_scale = float(self.layout_scale or 1.0)
        text_scale = float(self.text_scale or 1.0)
        icon_scale = float(self.icon_scale or 1.0)
        icon_base = list(app.emerald[:3] if positive else app.error[:3])
        icon_bg = icon_base + [0.24 if positive else 0.22]
        icon_line = icon_base + [0.34 if positive else 0.28]

        card = MDCard(
            size_hint_y=None,
            height=dp((98 if detail_text else 82) * layout_scale),
            radius=[dp(16 * layout_scale)],
            md_bg_color=app.ui_surface,
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
        icon_button = MDIconButton(
            icon=icon_name,
            pos_hint={"center_x": 0.5, "center_y": 0.5},
            size_hint=(None, None),
            size=(dp(22 * layout_scale), dp(22 * layout_scale)),
            theme_text_color="Custom",
            text_color=icon_color,
            user_font_size=f"{20 * icon_scale:.1f}sp",
            disabled=True,
        )
        icon_wrap.add_widget(icon_button)

        text_col = MDBoxLayout(orientation="vertical", spacing=dp(2 * layout_scale))
        text_col.add_widget(
            MDLabel(
                text=self._friendly_title(tx),
                font_style="Title",
                font_name=FONT_SEMIBOLD,
                font_size=sp(15 * text_scale),
                bold=True,
                theme_text_color="Custom",
                text_color=app.ui_text_primary,
                shorten=True,
                shorten_from="right",
            )
        )
        text_col.add_widget(
            MDLabel(
                text=self._friendly_time(str(tx.get("timestamp", "") or "")),
                font_style="Body",
                font_name=FONT_REGULAR,
                font_size=sp(11 * text_scale),
                theme_text_color="Custom",
                text_color=app.ui_text_secondary,
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
                    text_color=app.ui_text_secondary,
                    shorten=True,
                    shorten_from="right",
                )
            )

        amount_label = MDLabel(
            text=f"{sign} GHS {self._format_amount(abs(amount))}",
            size_hint_x=None,
            width=dp(124 * layout_scale),
            halign="right",
            valign="middle",
            font_name=FONT_SEMIBOLD,
            font_size=sp(15 * text_scale),
            bold=True,
            theme_text_color="Custom",
            text_color=app.emerald if positive else app.error,
        )

        row.add_widget(icon_wrap)
        row.add_widget(text_col)
        row.add_widget(amount_label)
        card.add_widget(row)
        return card

    def _render_recent_activity(self, rows: list[dict]):
        container = self.ids.recent_container
        container.clear_widgets()

        if not rows:
            sample = [
                {"type": "agent_deposit", "amount": 1000.0, "timestamp": datetime.now(timezone.utc).isoformat()},
                {"type": "transfer", "amount": -200.0, "timestamp": datetime.now(timezone.utc).isoformat()},
            ]
            rows = sample

        for tx in rows[:2]:
            container.add_widget(self._build_recent_item(tx))

    def _load_dashboard_worker(self, token: str):
        headers = {"Authorization": f"Bearer {token}"}
        wallet_data = {}
        tx_rows = []
        greeting_name = ""
        error_text = ""
        is_agent_valid = False
        agent_status = ""
        user_is_agent = False

        try:
            me_resp = requests.get(f"{API_URL}/auth/me", headers=headers, timeout=10)
            me_payload = me_resp.json() if me_resp.content else {}
            if me_resp.status_code < 400 and isinstance(me_payload, dict):
                first_name = str(me_payload.get("first_name", "") or "").strip()
                if not first_name:
                    full_name = str(me_payload.get("full_name", "") or "").strip()
                    if full_name:
                        first_name = full_name.split()[0]
                greeting_name = first_name
                user_is_agent = bool(me_payload.get("is_agent", False))
        except Exception:
            greeting_name = ""

        try:
            agent_resp = requests.get(f"{API_URL}/agents/me", headers=headers, timeout=10)
            agent_payload = agent_resp.json() if agent_resp.content else {}
            if agent_resp.status_code < 400 and isinstance(agent_payload, dict):
                agent_status = str(agent_payload.get("status", "") or "").strip().lower()
                is_agent_valid = agent_status == "active"
            elif isinstance(agent_payload, dict):
                detail = str(agent_payload.get("detail", "") or "").lower()
                if "not found" in detail or "not registered" in detail:
                    agent_status = "not_registered"
                elif "not active" in detail:
                    agent_status = "pending"
                elif "forbidden" in detail:
                    agent_status = "pending"
        except Exception:
            agent_status = agent_status or ""

        if user_is_agent and is_agent_valid:
            agent_status = "active"

        try:
            wallet_resp = requests.get(f"{API_URL}/wallet/me", headers=headers, timeout=10)
            wallet_payload = wallet_resp.json() if wallet_resp.content else {}
            if wallet_resp.status_code < 400 and isinstance(wallet_payload, dict):
                wallet_data = wallet_payload
            else:
                raw_detail = self._extract_detail(wallet_payload) or "Unable to load wallet balance."
                error_text = self._friendly_sync_message(raw_detail, "Unable to load wallet balance right now.")
        except Exception:
            error_text = "Connection issue. Check internet and try again."

        try:
            tx_resp = requests.get(f"{API_URL}/wallet/transactions/me?limit=8", headers=headers, timeout=10)
            tx_payload = tx_resp.json() if tx_resp.content else []
            if tx_resp.status_code < 400 and isinstance(tx_payload, list):
                tx_rows = tx_payload
            elif not error_text:
                raw_detail = self._extract_detail(tx_payload) or "Unable to load activity."
                error_text = self._friendly_sync_message(raw_detail, "Unable to load activity right now.")
        except Exception:
            if not error_text:
                error_text = "Unable to load activity right now."

        Clock.schedule_once(
            lambda _dt: self._apply_dashboard_data(
                wallet_data=wallet_data,
                tx_rows=tx_rows,
                error_text=error_text,
                greeting_name=greeting_name,
                is_agent_valid=is_agent_valid,
                agent_status=agent_status,
            )
        )

    def _apply_dashboard_data(
        self,
        wallet_data: dict,
        tx_rows: list[dict],
        error_text: str,
        greeting_name: str = "",
        is_agent_valid: bool = False,
        agent_status: str = "",
    ):
        self._is_loading = False
        self.is_agent_valid = bool(is_agent_valid)
        self.agent_quick_label = "Agent Dashboard" if self.is_agent_valid else "Become Agent"
        if greeting_name:
            self._set_greeting(greeting_name)

        if wallet_data:
            self.wallet_balance = float(wallet_data.get("balance", 0.0) or 0.0)
            self._update_balance_display()
            self.dashboard_status = "Updated just now"
        else:
            if self.wallet_balance == 0.0:
                self.wallet_balance = 5250.0
                self._update_balance_display()
            self.dashboard_status = error_text or "Demo wallet balance"

        if tx_rows:
            self._render_recent_activity(tx_rows)
        else:
            self._render_recent_activity([])
            if error_text:
                self.dashboard_status = error_text
                self._show_warning_popup(error_text)

    def load_dashboard_data(self):
        if self._is_loading:
            return

        app = MDApp.get_running_app()
        token = str(getattr(app, "access_token", "") or "").strip()
        pending_momo = str(getattr(app, "pending_momo", "") or "").strip()
        if pending_momo:
            self._set_greeting("" if pending_momo.isdigit() else pending_momo)

        if not token:
            self.wallet_balance = 5250.0
            self._update_balance_display()
            self.dashboard_status = "Demo mode. Sign in for live balance."
            self._render_recent_activity([])
            return

        self._is_loading = True
        self.dashboard_status = "Refreshing dashboard..."
        threading.Thread(target=self._load_dashboard_worker, args=(token,), daemon=True).start()

    def go_to_wallet(self):
        if self.manager:
            self.manager.current = "wallet"

    def go_to_deposit(self):
        if self.manager and self.manager.has_screen("deposit"):
            self.manager.current = "deposit"

    def go_to_withdraw(self):
        if self.manager and self.manager.has_screen("withdraw"):
            self.manager.current = "withdraw"

    def go_to_p2p_transfer(self):
        if self.manager:
            self.manager.current = "p2p_transfer"

    def go_to_agent(self):
        if self.is_agent_valid and self.manager and self.manager.has_screen("agent"):
            self.manager.current = "agent"
            return
        self._confirm_become_agent()

    def go_to_transactions(self):
        if self.manager:
            self.manager.current = "transactions"

    def go_to_settings(self):
        if self.manager:
            self.manager.current = "settings"

    def go_to_loans(self):
        if self.manager:
            self.manager.current = "loans"

    def go_to_investments(self):
        if self.manager:
            self.manager.current = "investments"

    @staticmethod
    def _safe_json(response):
        try:
            return response.json() if response.content else {}
        except Exception:
            text = (response.text or "").strip()
            return {"detail": sanitize_backend_message(text or f"HTTP {response.status_code}")}

    def _auth_headers(self) -> dict:
        app = MDApp.get_running_app()
        token = str(getattr(app, "access_token", "") or "").strip()
        return {"Authorization": f"Bearer {token}"} if token else {}

    def _friendly_agent_error(self, detail: str) -> str:
        message = str(detail or "").strip()
        normalized = message.lower()
        if "already an active agent" in normalized:
            return "Agent profile is already active. Opening Agent Dashboard."
        if "already an agent" in normalized:
            return "You already have an agent profile. We'll check its status."
        if "pending agent registration" in normalized:
            return "You already have a pending agent registration. Complete the Paystack payment to continue."
        if "payment verification failed" in normalized and "pending" in normalized:
            return "Payment is still processing. Please wait while we confirm your registration."
        if "a valid email or phone number is required" in normalized:
            return "Add a valid registered number or email to continue with agent registration."
        if "unauthorized" in normalized or "could not validate credentials" in normalized:
            return "Please sign in again to continue agent registration."
        return message or "Unable to complete agent registration right now."

    def _confirm_become_agent(self):
        self._close_more_actions_dialog()
        show_confirm_dialog(
            self,
            title="Become Agent",
            message=(
                f"Register as an agent with a one-time Paystack fee of GHS {AGENT_REGISTRATION_FEE_GHS:,.2f}. "
                f"After successful payment, GHS {AGENT_STARTUP_LOAN_GHS:,.2f} startup float "
                "is credited instantly as non-withdrawable capital."
            ),
            on_confirm=self._initiate_agent_registration,
            confirm_label="Pay GHS 100",
            cancel_label="Cancel",
        )

    def _initiate_agent_registration(self):
        headers = self._auth_headers()
        if not headers:
            show_message_dialog(
                self,
                title="Sign In Required",
                message="Please sign in first to register as an agent.",
                close_label="Close",
            )
            return

        self.dashboard_status = "Starting agent registration..."
        threading.Thread(
            target=self._initiate_agent_registration_worker,
            args=(headers,),
            daemon=True,
        ).start()

    def _initiate_agent_registration_worker(self, headers: dict):
        try:
            response = requests.post(f"{API_URL}/agents/register", headers=headers, timeout=15)
            payload = self._safe_json(response)
            if response.status_code < 400 and isinstance(payload, dict):
                reference = str(payload.get("reference", "") or "").strip()
                authorization_url = str(payload.get("authorization_url", "") or "").strip()
                message = str(payload.get("message", "") or "").strip()
                Clock.schedule_once(
                    lambda _dt: self._on_agent_registration_started(reference, authorization_url, message)
                )
                return

            detail = self._extract_detail(payload)
            Clock.schedule_once(lambda _dt: self._on_agent_registration_failed(detail))
        except Exception as exc:
            Clock.schedule_once(lambda _dt: self._on_agent_registration_failed(sanitize_backend_message(exc)))

    def _on_agent_registration_started(self, reference: str, authorization_url: str, message: str):
        self._last_agent_reference = reference
        friendly_message = (
            message
            or (
                f"Agent registration initialized. Pay GHS {AGENT_REGISTRATION_FEE_GHS:,.2f} with Paystack in the in-app checkout. "
                "If the window takes a few seconds to appear on a slow device, please wait. "
                f"After payment we will activate your Agent Dashboard and credit GHS {AGENT_STARTUP_LOAN_GHS:,.2f} startup float."
            )
        )
        self.dashboard_status = "Agent payment initialized. Waiting for confirmation..."
        show_message_dialog(
            self,
            title="Become Agent",
            message=friendly_message,
            close_label="Close",
        )

        if authorization_url:
            warmup_paystack_checkout(delay_seconds=0.0)
            opened_in_app = open_paystack_checkout(authorization_url, title="CYBER CASH Paystack", delay_seconds=0.0)
            if not opened_in_app:
                self._show_warning_popup("In-app Paystack checkout could not open. Please try again.")

        if reference:
            self._start_agent_registration_verification(reference)

    def _start_agent_registration_verification(self, reference: str):
        self._agent_verify_sequence += 1
        verify_sequence = self._agent_verify_sequence
        threading.Thread(
            target=self._poll_agent_registration_worker,
            args=(reference, verify_sequence),
            daemon=True,
        ).start()

    def _poll_agent_registration_worker(self, reference: str, verify_sequence: int):
        headers = self._auth_headers()
        for _ in range(AGENT_VERIFY_MAX_POLLS):
            if verify_sequence != self._agent_verify_sequence:
                return
            try:
                response = requests.get(
                    f"{API_URL}/agents/register/verify/{reference}",
                    headers=headers,
                    timeout=12,
                )
                payload = self._safe_json(response)

                if response.status_code < 400 and isinstance(payload, dict):
                    status_value = str(payload.get("status", "") or "").strip().lower()
                    if status_value == "active":
                        Clock.schedule_once(lambda _dt, p=payload: self._on_agent_registration_success(p))
                        return
                else:
                    detail = self._extract_detail(payload)
                    detail_lc = str(detail or "").lower()
                    if (
                        "pending" not in detail_lc
                        and "processing" not in detail_lc
                        and "queued" not in detail_lc
                        and "abandoned" not in detail_lc
                    ):
                        Clock.schedule_once(lambda _dt, d=detail: self._on_agent_registration_failed(d))
                        return
            except Exception:
                pass

            time.sleep(AGENT_VERIFY_POLL_INTERVAL_SECONDS)

        if verify_sequence == self._agent_verify_sequence:
            Clock.schedule_once(lambda _dt: self._on_agent_registration_timeout(reference))

    def _on_agent_registration_success(self, payload: dict):
        self.is_agent_valid = True
        self.agent_quick_label = "Agent Dashboard"
        self.dashboard_status = "Agent registration completed. Opening Agent Dashboard..."
        show_message_dialog(
            self,
            title="Agent Activated",
            message=(
                "Payment confirmed successfully.\n"
                f"GHS {AGENT_STARTUP_LOAN_GHS:,.2f} startup float was credited instantly "
                "as non-withdrawable agent capital."
            ),
            close_label="Open Dashboard",
            on_close=self._open_agent_dashboard,
        )
        self.load_dashboard_data()

    def _open_agent_dashboard(self):
        if self.manager and self.manager.has_screen("agent"):
            self.manager.current = "agent"

    def _on_agent_registration_failed(self, detail: str):
        detail_text = str(detail or "")
        detail_lc = detail_text.lower()
        if "already an active agent" in detail_lc:
            self.is_agent_valid = True
            self.agent_quick_label = "Agent Dashboard"
            self._open_agent_dashboard()
            return
        if "already an agent" in detail_lc:
            self._verify_existing_agent_status()
            return
        friendly = self._friendly_agent_error(detail)
        self.dashboard_status = "Agent registration failed."
        show_message_dialog(
            self,
            title="Registration Failed",
            message=friendly,
            close_label="Close",
        )

    def _verify_existing_agent_status(self):
        headers = self._auth_headers()
        if not headers:
            show_message_dialog(
                self,
                title="Sign In Required",
                message="Please sign in again to confirm your agent status.",
                close_label="Close",
            )
            return

        self.dashboard_status = "Checking agent status..."
        threading.Thread(
            target=self._verify_existing_agent_status_worker,
            args=(headers,),
            daemon=True,
        ).start()

    def _verify_existing_agent_status_worker(self, headers: dict):
        status_value = ""
        error_text = ""
        try:
            response = requests.get(f"{API_URL}/agents/me", headers=headers, timeout=12)
            payload = self._safe_json(response)
            if response.status_code < 400 and isinstance(payload, dict):
                status_value = str(payload.get("status", "") or "").strip().lower()
            else:
                error_text = self._extract_detail(payload) or "Unable to load agent profile."
        except Exception as exc:
            error_text = sanitize_backend_message(exc) or "Unable to load agent profile."

        Clock.schedule_once(
            lambda _dt: self._apply_verified_agent_status(status_value, error_text)
        )

    def _apply_verified_agent_status(self, status_value: str, error_text: str):
        if status_value == "active":
            self.is_agent_valid = True
            self.agent_quick_label = "Agent Dashboard"
            self.dashboard_status = "Agent status confirmed. Opening Agent Dashboard..."
            self._open_agent_dashboard()
            return

        self.is_agent_valid = False
        self.agent_quick_label = "Become Agent"
        if status_value == "pending":
            message = "Your agent registration is pending. Complete the Paystack payment to activate your Agent Dashboard."
            self.dashboard_status = "Agent registration pending."
        elif status_value:
            readable = status_value.replace("_", " ")
            message = f"Your agent status is {readable}. Please contact support if you need help activating."
            self.dashboard_status = "Agent registration not active."
        else:
            message = error_text or "Unable to confirm agent status right now."
            self.dashboard_status = "Agent status check failed."

        show_message_dialog(
            self,
            title="Agent Status",
            message=message,
            close_label="Close",
        )

    def _on_agent_registration_timeout(self, reference: str):
        self.dashboard_status = "Agent payment still processing."
        show_message_dialog(
            self,
            title="Still Processing",
            message=(
                "Your Paystack payment is still processing.\n"
                f"Reference: {reference}\n"
                "Please wait a moment and try again from Become Agent."
            ),
            close_label="Close",
        )

    def _close_more_actions_dialog(self, *_args):
        dialog = getattr(self, "_more_actions_dialog", None)
        if dialog is not None:
            try:
                dialog.dismiss()
            except Exception:
                pass
        self._more_actions_dialog = None

    def _navigate_more_action(self, screen_name: str):
        self._close_more_actions_dialog()
        if self.manager and self.manager.has_screen(screen_name):
            self.manager.current = screen_name

    def _open_btc_action(self):
        self._close_more_actions_dialog()
        if self.manager and self.manager.has_screen("btc"):
            self.manager.current = "btc"
            return
        show_message_dialog(
            self,
            title="BTC",
            message=(
                "BTC center is being finalized. "
                "You can continue using Wallet and Transactions while BTC UI is completed."
            ),
            close_label="Close",
        )

    def open_more_popup(self):
        self.open_more_actions()

    def open_more_actions(self):
        self._close_more_actions_dialog()

        app = MDApp.get_running_app()
        layout_scale = float(self.layout_scale or 1.0)
        text_scale = float(self.text_scale or 1.0)
        icon_scale = float(self.icon_scale or 1.0)
        compact_mode = Window.size[0] < 360

        menu_content = MDBoxLayout(
            orientation="vertical",
            spacing=dp(10 * layout_scale),
            adaptive_height=True,
            padding=[dp(2), dp(4), dp(2), 0],
        )
        menu_content.add_widget(
            MDLabel(
                text="Choose a service",
                adaptive_height=True,
                font_style="Title",
                font_name=FONT_SEMIBOLD,
                font_size=sp(15 * text_scale),
                bold=True,
                theme_text_color="Custom",
                text_color=app.ui_text_primary,
            )
        )
        menu_content.add_widget(
            MDLabel(
                text=(
                    "Airtime, data bundle, BTC, or open your agent dashboard."
                    if self.is_agent_valid
                    else "Airtime, data bundle, BTC, or become an agent."
                ),
                adaptive_height=True,
                font_style="Body",
                font_name=FONT_REGULAR,
                font_size=sp(11.5 * text_scale),
                theme_text_color="Custom",
                text_color=app.ui_text_secondary,
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
            icon_btn = MDIconButton(
                icon=icon_name,
                user_font_size=f"{30 * icon_scale:.1f}sp",
                size_hint=(None, None),
                size=(dp(36 * layout_scale), dp(36 * layout_scale)),
                pos_hint={"center_x": 0.5},
                theme_text_color="Custom",
                text_color=icon_color,
            )
            icon_btn.bind(on_release=_select)
            content.add_widget(icon_btn)
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
                    text_color=app.ui_text_primary,
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
                    text_color=app.ui_text_secondary,
                    shorten=True,
                    shorten_from="right",
                )
            )
            card.add_widget(content)
            grid.add_widget(card)

        def _open_agent_flow():
            self._close_more_actions_dialog()
            if self.is_agent_valid:
                self._navigate_more_action("agent")
                return
            self._confirm_become_agent()

        agent_label = "Agent Dashboard" if self.is_agent_valid else "Become Agent"
        agent_hint = (
            "Open your Agent Dashboard"
            if self.is_agent_valid
            else f"Pay GHS {AGENT_REGISTRATION_FEE_GHS:,.0f} with Paystack"
        )

        add_action_card(
            "Airtime",
            "Top up any network",
            "cellphone",
            list(app.gold),
            list(app.ui_surface_soft),
            [0.31, 0.48, 0.41, 0.42],
            lambda: self._navigate_more_action("airtime"),
        )
        add_action_card(
            "Data Bundle",
            "Buy data bundles",
            "wifi",
            list(app.emerald),
            list(app.ui_surface_soft),
            [0.35, 0.50, 0.41, 0.42],
            lambda: self._navigate_more_action("data_bundle"),
        )
        add_action_card(
            "BTC",
            "Open BTC center",
            "bitcoin",
            [0.97, 0.68, 0.15, 1],
            list(app.ui_glass),
            [0.53, 0.41, 0.23, 0.40],
            self._open_btc_action,
        )
        add_action_card(
            agent_label,
            agent_hint,
            "account-tie",
            list(app.gold),
            list(app.ui_surface),
            [0.20, 0.23, 0.28, 0.62],
            _open_agent_flow,
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

    def show_notifications(self):
        self._show_warning_popup("Notifications center is coming soon. Your account activity is still available below.")


Builder.load_string(KV)
