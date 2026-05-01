import os
import threading
import time
from datetime import datetime, timezone

import requests
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.metrics import dp, sp
from kivy.properties import BooleanProperty, NumericProperty, ObjectProperty, StringProperty
from kivy.uix.carousel import Carousel
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDIconButton
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel

from api.client import API_URL
from core.feedback_engine import tap_feedback
from core.message_sanitizer import extract_backend_message, sanitize_backend_message
from core.paystack_checkout import open_paystack_checkout, warmup_paystack_checkout
from core.popup_manager import show_confirm_dialog, show_custom_dialog, show_message_dialog
from core.responsive_screen import ResponsiveScreen
from storage import save_token

FONT_REGULAR = "Roboto"
FONT_SEMIBOLD = "Roboto"
FONT_BOLD = "Roboto"
POSITIVE_COLOR = [0.60, 0.88, 0.72, 1]
NEGATIVE_COLOR = [0.98, 0.48, 0.41, 1]
TX_CARD_BG = [0.09, 0.10, 0.12, 0.88]
AGENT_REGISTRATION_FEE_GHS = 100.0
AGENT_STARTUP_LOAN_GHS = 50.0
AGENT_VERIFY_POLL_INTERVAL_SECONDS = 3
AGENT_VERIFY_MAX_POLLS = 40

KV = """
#:import dp kivy.metrics.dp
#:import sp kivy.metrics.sp
#:set BG_OVERLAY (0.03, 0.03, 0.05, 0.90)
#:set GREEN_CARD (0.18, 0.36, 0.29, 0.95)
#:set GREEN_BTN (0.26, 0.43, 0.37, 0.95)
#:set GOLD (0.95, 0.80, 0.47, 1)
#:set GOLD_SOFT (0.92, 0.74, 0.36, 0.98)
#:set TEXT_MAIN (0.95, 0.94, 0.90, 1)
#:set FONT_REGULAR "Roboto"
#:set FONT_SEMI "Roboto"
#:set FONT_BOLD "Roboto"
<MoreActionsContent>:
    orientation: "vertical"
    adaptive_height: True
    spacing: dp(12 * root.layout_scale)
    padding: [dp(6 * root.layout_scale), dp(2 * root.layout_scale), dp(6 * root.layout_scale), dp(4 * root.layout_scale)]

    MDLabel:
        text: "Services"
        theme_text_color: "Custom"
        text_color: TEXT_MAIN
        font_name: FONT_SEMI
        font_size: sp(14 * root.text_scale)

    MDGridLayout:
        cols: 1 if root.compact_mode else 2
        adaptive_height: True
        row_default_height: dp(124 * root.layout_scale)
        row_force_default: True
        spacing: dp(10 * root.layout_scale)

        MDCard:
            radius: [dp(18 * root.layout_scale)]
            md_bg_color: [0.10, 0.16, 0.14, 0.96]
            line_color: [0.32, 0.49, 0.42, 0.50]
            elevation: 0
            padding: [dp(12 * root.layout_scale)] * 4
            on_release: root.trigger_action("airtime")

            MDBoxLayout:
                orientation: "vertical"
                spacing: dp(6 * root.layout_scale)

                MDCard:
                    size_hint: None, None
                    size: dp(44 * root.layout_scale), dp(44 * root.layout_scale)
                    radius: [dp(14 * root.layout_scale)]
                    md_bg_color: [0.16, 0.28, 0.24, 0.98]
                    elevation: 0

                    MDIcon:
                        icon: "cellphone"
                        theme_text_color: "Custom"
                        text_color: [0.72, 0.92, 0.76, 1]
                        font_size: sp(22 * root.icon_scale)
                        pos_hint: {"center_x": 0.5, "center_y": 0.5}

                MDLabel:
                    text: "Airtime"
                    theme_text_color: "Custom"
                    text_color: TEXT_MAIN
                    font_name: FONT_SEMI
                    font_size: sp(14 * root.text_scale)
                    size_hint_y: None
                    height: dp(18 * root.layout_scale)
                    shorten: True
                    shorten_from: "right"

                MDLabel:
                    text: "Top up fast"
                    theme_text_color: "Custom"
                    text_color: [0.72, 0.75, 0.78, 1]
                    font_name: FONT_REGULAR
                    font_size: sp(11 * root.text_scale)
                    size_hint_y: None
                    height: dp(14 * root.layout_scale)
                    shorten: True
                    shorten_from: "right"

        MDCard:
            radius: [dp(18 * root.layout_scale)]
            md_bg_color: [0.10, 0.16, 0.18, 0.96]
            line_color: [0.34, 0.47, 0.54, 0.52]
            elevation: 0
            padding: [dp(12 * root.layout_scale)] * 4
            on_release: root.trigger_action("data_bundle")

            MDBoxLayout:
                orientation: "vertical"
                spacing: dp(6 * root.layout_scale)

                MDCard:
                    size_hint: None, None
                    size: dp(44 * root.layout_scale), dp(44 * root.layout_scale)
                    radius: [dp(14 * root.layout_scale)]
                    md_bg_color: [0.14, 0.22, 0.28, 0.98]
                    elevation: 0

                    MDIcon:
                        icon: "access-point-network"
                        theme_text_color: "Custom"
                        text_color: [0.64, 0.86, 0.98, 1]
                        font_size: sp(22 * root.icon_scale)
                        pos_hint: {"center_x": 0.5, "center_y": 0.5}

                MDLabel:
                    text: "Data Bundle"
                    theme_text_color: "Custom"
                    text_color: TEXT_MAIN
                    font_name: FONT_SEMI
                    font_size: sp(14 * root.text_scale)
                    size_hint_y: None
                    height: dp(18 * root.layout_scale)
                    shorten: True
                    shorten_from: "right"

                MDLabel:
                    text: "Data fast"
                    theme_text_color: "Custom"
                    text_color: [0.72, 0.75, 0.78, 1]
                    font_name: FONT_REGULAR
                    font_size: sp(11 * root.text_scale)
                    size_hint_y: None
                    height: dp(14 * root.layout_scale)
                    shorten: True
                    shorten_from: "right"

        MDCard:
            radius: [dp(18 * root.layout_scale)]
            md_bg_color: [0.12, 0.18, 0.16, 0.96]
            line_color: [0.36, 0.52, 0.44, 0.50]
            elevation: 0
            padding: [dp(12 * root.layout_scale)] * 4
            on_release: root.trigger_action("airtime_2_cash")

            MDBoxLayout:
                orientation: "vertical"
                spacing: dp(6 * root.layout_scale)

                MDCard:
                    size_hint: None, None
                    size: dp(44 * root.layout_scale), dp(44 * root.layout_scale)
                    radius: [dp(14 * root.layout_scale)]
                    md_bg_color: [0.18, 0.30, 0.25, 0.98]
                    elevation: 0

                    MDIcon:
                        icon: "cash"
                        theme_text_color: "Custom"
                        text_color: [0.70, 0.92, 0.78, 1]
                        font_size: sp(22 * root.icon_scale)
                        pos_hint: {"center_x": 0.5, "center_y": 0.5}

                MDLabel:
                    text: "Airtime 2 Cash"
                    theme_text_color: "Custom"
                    text_color: TEXT_MAIN
                    font_name: FONT_SEMI
                    font_size: sp(14 * root.text_scale)
                    size_hint_y: None
                    height: dp(18 * root.layout_scale)
                    shorten: True
                    shorten_from: "right"

                MDLabel:
                    text: "Airtime to cash"
                    theme_text_color: "Custom"
                    text_color: [0.72, 0.75, 0.78, 1]
                    font_name: FONT_REGULAR
                    font_size: sp(11 * root.text_scale)
                    size_hint_y: None
                    height: dp(14 * root.layout_scale)
                    shorten: True
                    shorten_from: "right"

        MDCard:
            radius: [dp(18 * root.layout_scale)]
            md_bg_color: [0.13, 0.16, 0.20, 0.96]
            line_color: [0.38, 0.48, 0.58, 0.50]
            elevation: 0
            padding: [dp(12 * root.layout_scale)] * 4
            on_release: root.trigger_action("pay_bills")

            MDBoxLayout:
                orientation: "vertical"
                spacing: dp(6 * root.layout_scale)

                MDCard:
                    size_hint: None, None
                    size: dp(44 * root.layout_scale), dp(44 * root.layout_scale)
                    radius: [dp(14 * root.layout_scale)]
                    md_bg_color: [0.18, 0.22, 0.30, 0.98]
                    elevation: 0

                    MDIcon:
                        icon: "file-document-outline"
                        theme_text_color: "Custom"
                        text_color: [0.72, 0.86, 0.98, 1]
                        font_size: sp(22 * root.icon_scale)
                        pos_hint: {"center_x": 0.5, "center_y": 0.5}

                MDLabel:
                    text: "Pay Bills"
                    theme_text_color: "Custom"
                    text_color: TEXT_MAIN
                    font_name: FONT_SEMI
                    font_size: sp(14 * root.text_scale)
                    size_hint_y: None
                    height: dp(18 * root.layout_scale)
                    shorten: True
                    shorten_from: "right"

                MDLabel:
                    text: "Pay bills fast"
                    theme_text_color: "Custom"
                    text_color: [0.72, 0.75, 0.78, 1]
                    font_name: FONT_REGULAR
                    font_size: sp(11 * root.text_scale)
                    size_hint_y: None
                    height: dp(14 * root.layout_scale)
                    shorten: True
                    shorten_from: "right"

        MDCard:
            radius: [dp(18 * root.layout_scale)]
            md_bg_color: [0.16, 0.14, 0.10, 0.96]
            line_color: [0.53, 0.41, 0.23, 0.50]
            elevation: 0
            padding: [dp(12 * root.layout_scale)] * 4
            on_release: root.trigger_action("btc")

            MDBoxLayout:
                orientation: "vertical"
                spacing: dp(6 * root.layout_scale)

                MDCard:
                    size_hint: None, None
                    size: dp(44 * root.layout_scale), dp(44 * root.layout_scale)
                    radius: [dp(14 * root.layout_scale)]
                    md_bg_color: [0.28, 0.20, 0.10, 0.98]
                    elevation: 0

                    MDIcon:
                        icon: "bitcoin"
                        theme_text_color: "Custom"
                        text_color: [0.97, 0.68, 0.15, 1]
                        font_size: sp(22 * root.icon_scale)
                        pos_hint: {"center_x": 0.5, "center_y": 0.5}

                MDLabel:
                    text: "BTC"
                    theme_text_color: "Custom"
                    text_color: TEXT_MAIN
                    font_name: FONT_SEMI
                    font_size: sp(14 * root.text_scale)
                    size_hint_y: None
                    height: dp(18 * root.layout_scale)
                    shorten: True
                    shorten_from: "right"

                MDLabel:
                    text: "Crypto"
                    theme_text_color: "Custom"
                    text_color: [0.72, 0.75, 0.78, 1]
                    font_name: FONT_REGULAR
                    font_size: sp(11 * root.text_scale)
                    size_hint_y: None
                    height: dp(14 * root.layout_scale)
                    shorten: True
                    shorten_from: "right"

        MDCard:
            radius: [dp(18 * root.layout_scale)]
            md_bg_color: [0.12, 0.14, 0.16, 0.96]
            line_color: [0.62, 0.52, 0.30, 0.48]
            elevation: 0
            padding: [dp(12 * root.layout_scale)] * 4
            on_release: root.trigger_action("agent")

            MDBoxLayout:
                orientation: "vertical"
                spacing: dp(6 * root.layout_scale)

                MDCard:
                    size_hint: None, None
                    size: dp(44 * root.layout_scale), dp(44 * root.layout_scale)
                    radius: [dp(14 * root.layout_scale)]
                    md_bg_color: [0.22, 0.18, 0.11, 0.98]
                    elevation: 0

                    MDIcon:
                        icon: "account-tie"
                        theme_text_color: "Custom"
                        text_color: GOLD
                        font_size: sp(22 * root.icon_scale)
                        pos_hint: {"center_x": 0.5, "center_y": 0.5}

                MDLabel:
                    text: root.agent_action_label
                    theme_text_color: "Custom"
                    text_color: TEXT_MAIN
                    font_name: FONT_SEMI
                    font_size: sp(13.5 * root.text_scale)
                    size_hint_y: None
                    height: dp(18 * root.layout_scale)
                    shorten: True
                    shorten_from: "right"

                MDLabel:
                    text: root.agent_fee_hint
                    theme_text_color: "Custom"
                    text_color: [0.72, 0.75, 0.78, 1]
                    font_name: FONT_REGULAR
                    font_size: sp(11 * root.text_scale)
                    size_hint_y: None
                    height: dp(14 * root.layout_scale)
                    shorten: True
                    shorten_from: "right"

<HomeScreen>:
    MDBoxLayout:
        orientation: "vertical"

        canvas.before:
            Color:
                rgba: app.ui_background
            Rectangle:
                pos: self.pos
                size: self.size
            Color:
                rgba: (1, 1, 1, 0.10) if app.theme_mode == "Dark" else (1, 1, 1, 0.0)
            Rectangle:
                pos: self.pos
                size: self.size
                source: root.background_source
            Color:
                rgba: app.ui_overlay
            Rectangle:
                pos: self.pos
                size: self.size
            Color:
                rgba: 0.42, 0.32, 0.14, 0.10 if app.theme_mode == "Dark" else 0.05
            Ellipse:
                pos: self.x + self.width * 0.16, self.y + self.height * 0.74
                size: self.width * 0.66, self.width * 0.66
            Color:
                rgba: 0.25, 0.39, 0.32, 0.16 if app.theme_mode == "Dark" else 0.08
            Ellipse:
                pos: self.x + self.width * 0.38, self.y + self.height * 0.16
                size: self.width * 0.62, self.width * 0.62

        ScrollView:
            do_scroll_x: False
            bar_width: 0

            MDBoxLayout:
                orientation: "vertical"
                size_hint_y: None
                height: self.minimum_height
                padding: [dp(16 * root.layout_scale), dp(14 * root.layout_scale), dp(16 * root.layout_scale), dp(16 * root.layout_scale)]
                spacing: dp(12 * root.layout_scale)

                MDBoxLayout:
                    size_hint_y: None
                    height: dp(64 * root.layout_scale)

                    MDCard:
                        size_hint: None, None
                        size: dp(52 * root.layout_scale), dp(52 * root.layout_scale)
                        radius: [dp(26 * root.layout_scale)]
                        md_bg_color: [0.10, 0.11, 0.14, 0.86]
                        line_color: [0.48, 0.40, 0.26, 0.28]
                        elevation: 0
                        on_release: root.go_to("settings")

                        FitImage:
                            source: root.avatar_source
                            radius: [dp(22 * root.layout_scale)]
                            pos_hint: {"center_x": 0.5, "center_y": 0.5}

                    MDLabel:
                        text: "CYBER CASH"
                        halign: "center"
                        theme_text_color: "Custom"
                        text_color: app.gold
                        font_name: FONT_BOLD
                        font_style: "Title"
                        font_size: sp(24 * root.text_scale)
                        bold: True

                    FloatLayout:
                        size_hint: None, None
                        size: dp(88 * root.layout_scale), dp(54 * root.layout_scale)

                        MDIconButton:
                            id: theme_toggle_button
                            icon: root.theme_toggle_icon
                            user_font_size: str(24 * root.icon_scale) + "sp"
                            pos_hint: {"center_x": 0.24, "center_y": 0.58}
                            theme_text_color: "Custom"
                            text_color: app.ui_text_primary
                            on_release: root.toggle_theme()

                        MDIconButton:
                            icon: "bell-ring-outline"
                            user_font_size: str(26 * root.icon_scale) + "sp"
                            pos_hint: {"center_x": 0.68, "center_y": 0.58}
                            theme_text_color: "Custom"
                            text_color: app.gold
                            on_release: root.go_to("transactions")

                        MDCard:
                            size_hint: None, None
                            size: dp(18 * root.layout_scale), dp(18 * root.layout_scale)
                            radius: [dp(9 * root.layout_scale)]
                            md_bg_color: [0.85, 0.15, 0.12, 0.98]
                            pos_hint: {"center_x": 0.90, "center_y": 0.80}
                            elevation: 0
                            opacity: 1 if root.notification_badge_visible else 0

                            MDLabel:
                                text: root.notification_count_text
                                halign: "center"
                                valign: "middle"
                                font_name: FONT_BOLD
                                font_size: sp(10 * root.text_scale)
                                theme_text_color: "Custom"
                                text_color: 1, 1, 1, 1
                                bold: True

                MDBoxLayout:
                    size_hint_y: None
                    height: "1dp"
                    canvas.before:
                        Color:
                            rgba: 0.62, 0.62, 0.64, 0.20
                        Rectangle:
                            pos: self.pos
                            size: self.size
                        Color:
                            rgba: 0.97, 0.82, 0.50, 0.88
                        Rectangle:
                            pos: self.center_x - self.width * 0.18, self.y
                            size: self.width * 0.36, self.height
                        Color:
                            rgba: 0.96, 0.82, 0.48, 0.20
                        Rectangle:
                            pos: self.center_x - self.width * 0.28, self.y - dp(1)
                            size: self.width * 0.56, dp(3)

                MDBoxLayout:
                    size_hint_y: None
                    height: dp(40 * root.layout_scale)
                    spacing: dp(10 * root.layout_scale)

                    MDCard:
                        size_hint: None, None
                        size: dp(34 * root.layout_scale), dp(34 * root.layout_scale)
                        radius: [dp(10 * root.layout_scale)]
                        md_bg_color: [0.64, 0.49, 0.20, 0.36]
                        elevation: 0

                        MDIcon:
                            icon: "card-account-details-outline"
                            theme_text_color: "Custom"
                            text_color: GOLD
                            font_size: sp(19 * root.icon_scale)
                            pos_hint: {"center_x": 0.5, "center_y": 0.5}

                    MDLabel:
                        text: root.greeting_text
                        theme_text_color: "Custom"
                        text_color: app.ui_text_primary
                        font_name: FONT_SEMI
                        font_size: sp(17 * root.text_scale)
                        shorten: True
                        shorten_from: "right"

                MDBoxLayout:
                    orientation: "vertical"
                    size_hint_y: None
                    height: dp(242 * root.layout_scale)
                    spacing: dp(8 * root.layout_scale)

                    MDBoxLayout:
                        size_hint_y: None
                        height: dp(24 * root.layout_scale)

                        MDLabel:
                            text: "Portfolio"
                            theme_text_color: "Custom"
                            text_color: app.gold
                            font_name: FONT_BOLD
                            font_size: sp(15 * root.text_scale)
                            bold: True
                            size_hint_x: 1

                        MDIconButton:
                            icon: "eye-off-outline" if root.balance_hidden else "eye-outline"
                            user_font_size: str(20 * root.icon_scale) + "sp"
                            size_hint: None, None
                            size: dp(24 * root.layout_scale), dp(24 * root.layout_scale)
                            pos_hint: {"center_y": 0.5}
                            theme_text_color: "Custom"
                            text_color: app.ui_text_secondary
                            on_release: root.toggle_balance()

                        MDLabel:
                            text: str(int(root.portfolio_index) + 1) + "/3"
                            theme_text_color: "Custom"
                            text_color: app.ui_text_secondary
                            font_name: FONT_SEMI
                            font_size: sp(12 * root.text_scale)
                            halign: "right"
                            text_size: self.size
                            size_hint_x: None
                            width: dp(44 * root.layout_scale)

                    Carousel:
                        id: portfolio_carousel
                        direction: "right"
                        loop: True
                        anim_move_duration: 0.22
                        on_index: root._on_portfolio_carousel_index(self.index)

                    MDBoxLayout:
                        size_hint_y: None
                        height: dp(10 * root.layout_scale)
                        spacing: dp(6 * root.layout_scale)
                        size_hint_x: None
                        width: dp(42 * root.layout_scale)
                        pos_hint: {"center_x": 0.5}

                        Widget:
                            size_hint: None, None
                            size: dp(8 * root.layout_scale), dp(8 * root.layout_scale)
                            canvas.before:
                                Color:
                                    rgba: app.gold if root.portfolio_index == 0 else app.ui_text_secondary
                                RoundedRectangle:
                                    pos: self.pos
                                    size: self.size
                                    radius: [dp(4 * root.layout_scale)]

                        Widget:
                            size_hint: None, None
                            size: dp(8 * root.layout_scale), dp(8 * root.layout_scale)
                            canvas.before:
                                Color:
                                    rgba: app.gold if root.portfolio_index == 1 else app.ui_text_secondary
                                RoundedRectangle:
                                    pos: self.pos
                                    size: self.size
                                    radius: [dp(4 * root.layout_scale)]

                        Widget:
                            size_hint: None, None
                            size: dp(8 * root.layout_scale), dp(8 * root.layout_scale)
                            canvas.before:
                                Color:
                                    rgba: app.gold if root.portfolio_index == 2 else app.ui_text_secondary
                                RoundedRectangle:
                                    pos: self.pos
                                    size: self.size
                                    radius: [dp(4 * root.layout_scale)]

                MDBoxLayout:
                    size_hint_y: None
                    height: dp(84 * root.layout_scale)
                    spacing: dp(12 * root.layout_scale)

                    MDCard:
                        radius: [dp(20 * root.layout_scale)]
                        md_bg_color: app.gold
                        line_color: [0.98, 0.86, 0.60, 0.72]
                        elevation: 0
                        padding: [dp(10 * root.layout_scale), dp(8 * root.layout_scale), dp(14 * root.layout_scale), dp(8 * root.layout_scale)]
                        on_release: root.go_to("deposit")

                        canvas.before:
                            Color:
                                rgba: 1, 0.95, 0.76, 0.14
                            RoundedRectangle:
                                pos: self.x + dp(2), self.top - self.height * 0.30
                                size: self.width - dp(4), self.height * 0.22
                                radius: [dp(18 * root.layout_scale)]

                        MDBoxLayout:
                            spacing: dp(10 * root.layout_scale)

                            MDCard:
                                size_hint: None, None
                                size: dp(38 * root.layout_scale), dp(38 * root.layout_scale)
                                radius: [dp(11 * root.layout_scale)]
                                md_bg_color: [0.58, 0.40, 0.15, 0.58]
                                elevation: 0

                                MDIcon:
                                    icon: "plus"
                                    theme_text_color: "Custom"
                                    text_color: [0.16, 0.12, 0.07, 1]
                                    font_size: sp(20 * root.icon_scale)
                                    pos_hint: {"center_x": 0.5, "center_y": 0.5}

                            MDLabel:
                                text: "Deposit"
                                theme_text_color: "Custom"
                                text_color: [0, 0, 0, 1]
                                font_name: FONT_BOLD
                                font_size: sp(17 * root.text_scale)
                                bold: True

                    MDCard:
                        radius: [dp(20 * root.layout_scale)]
                        md_bg_color: GREEN_BTN
                        line_color: [0.58, 0.80, 0.68, 0.56]
                        elevation: 0
                        padding: [dp(10 * root.layout_scale), dp(8 * root.layout_scale), dp(14 * root.layout_scale), dp(8 * root.layout_scale)]
                        on_release: root.go_to("withdraw")

                        canvas.before:
                            Color:
                                rgba: 0.86, 0.96, 0.88, 0.08
                            RoundedRectangle:
                                pos: self.x + dp(2), self.top - self.height * 0.30
                                size: self.width - dp(4), self.height * 0.22
                                radius: [dp(18 * root.layout_scale)]

                        MDBoxLayout:
                            spacing: dp(10 * root.layout_scale)

                            MDCard:
                                size_hint: None, None
                                size: dp(38 * root.layout_scale), dp(38 * root.layout_scale)
                                radius: [dp(11 * root.layout_scale)]
                                md_bg_color: [0.10, 0.24, 0.19, 0.84]
                                elevation: 0

                                MDIcon:
                                    icon: "arrow-top-right"
                                    theme_text_color: "Custom"
                                    text_color: [0.78, 0.93, 0.76, 1]
                                    font_size: sp(20 * root.icon_scale)
                                    pos_hint: {"center_x": 0.5, "center_y": 0.5}

                            MDLabel:
                                text: "Withdraw"
                                theme_text_color: "Custom"
                                text_color: [0.96, 0.94, 0.88, 1]
                                font_name: FONT_BOLD
                                font_size: sp(17 * root.text_scale)
                                bold: True

                MDBoxLayout:
                    adaptive_height: True

                    MDLabel:
                        text: "Actions"
                        theme_text_color: "Custom"
                        text_color: app.gold
                        font_name: FONT_BOLD
                        font_size: sp(20 * root.text_scale)

                    MDTextButton:
                        text: "All"
                        theme_text_color: "Custom"
                        text_color: app.gold
                        font_name: FONT_SEMI
                        font_size: sp(15 * root.text_scale)
                        on_release: root.go_to("settings")

                MDGridLayout:
                    cols: root.quick_action_cols
                    adaptive_height: True
                    row_default_height: dp(112 * root.layout_scale)
                    row_force_default: True
                    spacing: dp(10 * root.layout_scale)

                    MDCard:
                        radius: [dp(16 * root.layout_scale)]
                        md_bg_color: [0.09, 0.16, 0.15, 0.84]
                        line_color: [0.32, 0.49, 0.42, 0.42]
                        elevation: 0
                        padding: [dp(4 * root.layout_scale)] * 4
                        on_release: root.go_to("p2p_transfer")

                        MDBoxLayout:
                            orientation: "vertical"
                            spacing: 0

                            MDIconButton:
                                icon: "send"
                                user_font_size: str(31 * root.icon_scale) + "sp"
                                pos_hint: {"center_x": 0.5}
                                theme_text_color: "Custom"
                                text_color: [0.55, 0.84, 0.66, 1]
                                on_release: root.go_to("p2p_transfer")

                            MDLabel:
                                text: "Send"
                                halign: "center"
                                theme_text_color: "Custom"
                                text_color: TEXT_MAIN
                                font_name: FONT_SEMI
                                font_size: sp(12.5 * root.text_scale)

                    MDCard:
                        radius: [dp(16 * root.layout_scale)]
                        md_bg_color: [0.10, 0.17, 0.15, 0.84]
                        line_color: [0.35, 0.50, 0.42, 0.42]
                        elevation: 0
                        padding: [dp(4 * root.layout_scale)] * 4
                        on_release: root.go_to("investments")

                        MDBoxLayout:
                            orientation: "vertical"
                            spacing: 0

                            MDIconButton:
                                icon: "finance"
                                user_font_size: str(31 * root.icon_scale) + "sp"
                                pos_hint: {"center_x": 0.5}
                                theme_text_color: "Custom"
                                text_color: [0.91, 0.75, 0.44, 1]
                                on_release: root.go_to("investments")

                            MDLabel:
                                text: "Invest"
                                halign: "center"
                                theme_text_color: "Custom"
                                text_color: TEXT_MAIN
                                font_name: FONT_SEMI
                                font_size: sp(12.5 * root.text_scale)

                    MDCard:
                        radius: [dp(16 * root.layout_scale)]
                        md_bg_color: [0.10, 0.16, 0.14, 0.84]
                        line_color: [0.34, 0.48, 0.40, 0.38]
                        elevation: 0
                        padding: [dp(4 * root.layout_scale)] * 4
                        on_release: root.go_to("loans")

                        MDBoxLayout:
                            orientation: "vertical"
                            spacing: 0

                            MDIconButton:
                                icon: "shield-check-outline"
                                user_font_size: str(31 * root.icon_scale) + "sp"
                                pos_hint: {"center_x": 0.5}
                                theme_text_color: "Custom"
                                text_color: [0.83, 0.92, 0.60, 1]
                                on_release: root.go_to("loans")

                            MDLabel:
                                text: "Loan"
                                halign: "center"
                                theme_text_color: "Custom"
                                text_color: TEXT_MAIN
                                font_name: FONT_SEMI
                                font_size: sp(12.5 * root.text_scale)

                    MDCard:
                        radius: [dp(16 * root.layout_scale)]
                        md_bg_color: [0.16, 0.14, 0.10, 0.84]
                        line_color: [0.53, 0.41, 0.23, 0.40]
                        elevation: 0
                        padding: [dp(4 * root.layout_scale)] * 4
                        on_release: root.open_more_actions()

                        MDBoxLayout:
                            orientation: "vertical"
                            spacing: 0

                            MDIconButton:
                                icon: "view-grid"
                                user_font_size: str(31 * root.icon_scale) + "sp"
                                pos_hint: {"center_x": 0.5}
                                theme_text_color: "Custom"
                                text_color: [0.90, 0.75, 0.43, 1]
                                on_release: root.open_more_actions()

                            MDLabel:
                                text: "More"
                                halign: "center"
                                theme_text_color: "Custom"
                                text_color: TEXT_MAIN
                                font_name: FONT_SEMI
                                font_size: sp(12.5 * root.text_scale)

                MDBoxLayout:
                    adaptive_height: True

                    MDLabel:
                        text: "Recent Activity"
                        theme_text_color: "Custom"
                        text_color: app.ui_text_primary
                        font_name: FONT_BOLD
                        font_size: sp(20 * root.text_scale)

                    MDTextButton:
                        text: "All"
                        theme_text_color: "Custom"
                        text_color: app.gold
                        font_name: FONT_SEMI
                        font_size: sp(15 * root.text_scale)
                        on_release: root.go_to("transactions")

                MDBoxLayout:
                    id: recent_container
                    orientation: "vertical"
                    adaptive_height: True
                    spacing: dp(10 * root.layout_scale)

                MDBoxLayout:
                    size_hint_y: None
                    height: dp(14 * root.layout_scale)
                    spacing: dp(8 * root.layout_scale)
                    size_hint_x: None
                    width: dp(92 * root.layout_scale)
                    pos_hint: {"center_x": 0.5}

                    Widget:
                        canvas.before:
                            Color:
                                rgba: GOLD
                            RoundedRectangle:
                                pos: self.x + dp(2), self.center_y - dp(2)
                                size: self.width - dp(4), dp(4)
                                radius: [dp(2)]

                    Widget:
                        canvas.before:
                            Color:
                                rgba: 0.45, 0.42, 0.34, 0.56
                            RoundedRectangle:
                                pos: self.x + dp(2), self.center_y - dp(2)
                                size: self.width - dp(4), dp(4)
                                radius: [dp(2)]

                    Widget:
                        canvas.before:
                            Color:
                                rgba: 0.45, 0.42, 0.34, 0.56
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


class HomeScreen(ResponsiveScreen):
    avatar_source = StringProperty("")
    background_source = StringProperty("")
    greeting_text = StringProperty("Hello, John")
    notification_count_text = StringProperty("1")
    notification_badge_visible = BooleanProperty(True)
    portfolio_index = NumericProperty(0)
    theme_toggle_icon = StringProperty("weather-night")
    wallet_balance_amount = NumericProperty(5250.0)
    balance_hidden = BooleanProperty(False)
    balance_display = StringProperty("GHS 5,250.00")
    balance_status = StringProperty("Demo balance")
    is_agent_active = BooleanProperty(False)
    agent_action_label = StringProperty("Become Agent")
    agent_action_hint = StringProperty(f"Pay GHS {AGENT_REGISTRATION_FEE_GHS:,.0f}")
    _is_loading = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.avatar_source = self._resolve_avatar_source()
        self.background_source = self._resolve_asset_source("kivy_frontend/assets/background.png")
        self._update_balance_display()
        self._more_actions_popup = None
        self._agent_verify_sequence = 0
        self._last_agent_reference = ""
        self._portfolio_carousel_ready = False
        self._portfolio_cards: dict[str, dict[str, object]] = {}

    def on_kv_post(self, _base_widget):
        super().on_kv_post(_base_widget)
        Clock.schedule_once(lambda _dt: self._prime_premium_ui(), 0)

    def on_pre_enter(self):
        self._sync_theme_toggle_icon()
        self._build_portfolio_carousel(force=True)
        self.load_home_data()

    def on_leave(self, *_args):
        self._agent_verify_sequence += 1
        self.close_more_actions()

    @staticmethod
    def _resolve_avatar_source() -> str:
        return HomeScreen._resolve_asset_source(
            "assets/avatar.png",
            "kivy_frontend/assets/avatar.png",
            "kivy_frontend/assets/avatars/0249945389.png",
        )

    @staticmethod
    def _resolve_asset_source(*candidates: str) -> str:
        for candidate in candidates:
            if os.path.exists(candidate):
                return candidate
        return ""

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

    def _update_balance_display(self) -> None:
        if self.balance_hidden:
            self.balance_display = "GHS ****.**"
        else:
            self.balance_display = f"GHS {float(self.wallet_balance_amount or 0.0):,.2f}"

    def _set_agent_action_state(self, is_active: bool) -> None:
        self.is_agent_active = bool(is_active)
        if self.is_agent_active:
            self.agent_action_label = "Agent Dashboard"
            self.agent_action_hint = "Open Agent Dashboard"
        else:
            self.agent_action_label = "Become Agent"
            self.agent_action_hint = f"Pay GHS {AGENT_REGISTRATION_FEE_GHS:,.0f}"

    def toggle_balance(self) -> None:
        tap_feedback()
        self.balance_hidden = not self.balance_hidden
        self._update_balance_display()
        self._refresh_portfolio_values()
        wallet_card = (self._portfolio_cards.get("wallet") or {}).get("card")
        self._pulse_widget(wallet_card)

    def toggle_theme(self) -> None:
        tap_feedback()
        app = MDApp.get_running_app()
        if app and hasattr(app, "toggle_theme"):
            app.toggle_theme()
        self._sync_theme_toggle_icon()
        self._build_portfolio_carousel(force=True)
        self._refresh_portfolio_values()
        self._pulse_widget(self.ids.get("theme_toggle_button"))

    def _prime_premium_ui(self) -> None:
        self._sync_theme_toggle_icon()
        self._build_portfolio_carousel(force=True)
        self._refresh_portfolio_values()

    def _sync_theme_toggle_icon(self) -> None:
        app = MDApp.get_running_app()
        mode = str(getattr(app, "theme_mode", getattr(getattr(app, "theme_cls", None), "theme_style", "Dark")) or "Dark")
        self.theme_toggle_icon = "weather-sunny" if mode.lower() == "dark" else "weather-night"

    def _theme_value(self, key: str, fallback):
        app = MDApp.get_running_app()
        value = getattr(app, key, fallback) if app else fallback
        if isinstance(value, (list, tuple)):
            return list(value)
        return value

    def _pulse_widget(self, widget, *, opacity: float = 0.86) -> None:
        if widget is None:
            return
        try:
            Animation.cancel_all(widget, "opacity")
            anim = Animation(opacity=opacity, duration=0.08, t="out_quad") + Animation(opacity=1.0, duration=0.14, t="out_quad")
            anim.start(widget)
        except Exception:
            pass

    def _on_portfolio_carousel_index(self, index: int) -> None:
        try:
            new_index = max(0, min(2, int(index or 0)))
        except Exception:
            new_index = 0
        if new_index == self.portfolio_index:
            return
        self.portfolio_index = new_index
        tap_feedback(sound=False)
        key_map = {0: "wallet", 1: "btc", 2: "virtual_card"}
        card_info = self._portfolio_cards.get(key_map.get(new_index, ""))
        if card_info:
            self._pulse_widget(card_info.get("card"))

    def _portfolio_specs(self) -> list[dict]:
        app = MDApp.get_running_app()
        gold = list(getattr(app, "gold", [0.95, 0.80, 0.47, 1]))
        emerald = list(getattr(app, "emerald", [0.26, 0.78, 0.56, 1]))
        btc = list(getattr(app, "btc", [0.97, 0.68, 0.15, 1]))
        text_primary = list(getattr(app, "ui_text_primary", [0.96, 0.96, 0.98, 1]))
        text_secondary = list(getattr(app, "ui_text_secondary", [0.74, 0.76, 0.80, 1]))
        theme_mode = str(getattr(app, "theme_mode", "Dark") or "Dark")
        light_mode = theme_mode.lower() == "light"
        value_surface = "Swipe premium cards"
        return [
            {
                "key": "wallet",
                "title": "Wallet Vault",
                "value": self.balance_display,
                "subtitle": "Move money fast.",
                "caption": "Tap to open Wallet",
                "icon": "wallet-outline",
                "accent": gold,
                "accent_bg": [gold[0], gold[1], gold[2], 0.20 if not light_mode else 0.16],
                "target": lambda: self.go_to("wallet"),
                "value_color": gold,
                "caption_color": text_secondary,
                "hint": value_surface,
            },
            {
                "key": "btc",
                "title": "BTC Desk",
                "value": "0.0000 BTC",
                "subtitle": "Track crypto fast.",
                "caption": "Tap to open BTC",
                "icon": "bitcoin",
                "accent": btc,
                "accent_bg": [btc[0], btc[1], btc[2], 0.18 if not light_mode else 0.14],
                "target": lambda: self.go_to("btc"),
                "value_color": btc,
                "caption_color": text_secondary,
                "hint": "Fast crypto access",
            },
            {
                "key": "virtual_card",
                "title": "Virtual Card",
                "value": "Instant Spend Mode",
                "subtitle": "Cards and controls.",
                "caption": "Tap to open Cards",
                "icon": "credit-card-outline",
                "accent": emerald,
                "accent_bg": [emerald[0], emerald[1], emerald[2], 0.18 if not light_mode else 0.14],
                "target": lambda: self.go_to("cards"),
                "value_color": emerald,
                "caption_color": text_secondary,
                "hint": "Swipe to the next card",
            },
        ]

    def _build_portfolio_card(self, spec: dict) -> MDBoxLayout:
        layout_scale = float(self.layout_scale or 1.0)
        text_scale = float(self.text_scale or 1.0)
        icon_scale = float(self.icon_scale or 1.0)

        page = MDBoxLayout(
            orientation="vertical",
            padding=[dp(4 * layout_scale), 0, dp(4 * layout_scale), 0],
            size_hint_y=1,
        )

        card = MDCard(
            radius=[dp(26 * layout_scale)],
            md_bg_color=list(self._theme_value("ui_glass", [1, 1, 1, 0.05])),
            line_color=list(self._theme_value("ui_glass_border", [1, 1, 1, 0.10])),
            elevation=0,
            padding=[dp(16 * layout_scale), dp(16 * layout_scale), dp(16 * layout_scale), dp(16 * layout_scale)],
        )
        card.bind(on_release=lambda *_args, action=spec["target"]: action())

        content = MDBoxLayout(orientation="vertical", spacing=dp(10 * layout_scale))

        top_row = MDBoxLayout(size_hint_y=None, height=dp(54 * layout_scale), spacing=dp(12 * layout_scale))
        icon_shell = MDCard(
            size_hint=(None, None),
            size=(dp(44 * layout_scale), dp(44 * layout_scale)),
            radius=[dp(15 * layout_scale)],
            md_bg_color=list(spec["accent_bg"]),
            line_color=[spec["accent"][0], spec["accent"][1], spec["accent"][2], 0.32],
            elevation=0,
        )
        icon_shell.add_widget(
            MDIconButton(
                icon=spec["icon"],
                user_font_size=f"{24 * icon_scale:.1f}sp",
                size_hint=(None, None),
                size=(dp(26 * layout_scale), dp(26 * layout_scale)),
                pos_hint={"center_x": 0.5, "center_y": 0.5},
                theme_text_color="Custom",
                text_color=spec["accent"],
            )
        )

        title_stack = MDBoxLayout(orientation="vertical", spacing=dp(2 * layout_scale))
        title_stack.add_widget(
            MDLabel(
                text=spec["title"],
                theme_text_color="Custom",
                text_color=list(self._theme_value("ui_text_primary", [0.96, 0.96, 0.98, 1])),
                font_name=FONT_BOLD,
                font_size=sp(16 * text_scale),
                bold=True,
                shorten=True,
                shorten_from="right",
            )
        )
        title_stack.add_widget(
            MDLabel(
                text=spec["subtitle"],
                theme_text_color="Custom",
                text_color=list(self._theme_value("ui_text_secondary", [0.74, 0.76, 0.80, 1])),
                font_name=FONT_REGULAR,
                font_size=sp(11.5 * text_scale),
                shorten=True,
                shorten_from="right",
            )
        )
        top_row.add_widget(icon_shell)
        top_row.add_widget(title_stack)

        value_label = MDLabel(
            text=spec["value"],
            theme_text_color="Custom",
            text_color=spec["value_color"],
            font_name=FONT_BOLD,
            font_style="Headline",
            font_size=sp(32 * text_scale),
            bold=True,
            shorten=True,
            shorten_from="right",
        )
        hint_label = MDLabel(
            text=spec["hint"],
            theme_text_color="Custom",
            text_color=list(self._theme_value("ui_text_secondary", [0.74, 0.76, 0.80, 1])),
            font_name=FONT_SEMIBOLD,
            font_size=sp(11 * text_scale),
            shorten=True,
            shorten_from="right",
        )
        caption_label = MDLabel(
            text=spec["caption"],
            theme_text_color="Custom",
            text_color=spec["caption_color"],
            font_name=FONT_SEMIBOLD,
            font_size=sp(12 * text_scale),
            shorten=True,
            shorten_from="right",
        )

        content.add_widget(top_row)
        content.add_widget(value_label)
        content.add_widget(hint_label)
        content.add_widget(caption_label)
        card.add_widget(content)
        page.add_widget(card)

        self._portfolio_cards[spec["key"]] = {
            "card": card,
            "value_label": value_label,
            "hint_label": hint_label,
            "caption_label": caption_label,
        }
        return page

    def _build_portfolio_carousel(self, force: bool = False) -> None:
        carousel = self.ids.get("portfolio_carousel")
        if carousel is None:
            return
        if self._portfolio_carousel_ready and not force:
            return

        carousel.clear_widgets()
        self._portfolio_cards = {}
        for spec in self._portfolio_specs():
            carousel.add_widget(self._build_portfolio_card(spec))

        self._portfolio_carousel_ready = True
        self._refresh_portfolio_values()

    def _refresh_portfolio_values(self) -> None:
        wallet = self._portfolio_cards.get("wallet")
        if wallet:
            wallet_label = wallet.get("value_label")
            if wallet_label is not None:
                wallet_label.text = self.balance_display
            hint_label = wallet.get("hint_label")
            if hint_label is not None:
                hint_label.text = self.balance_status or "Swipe premium cards"

    @staticmethod
    def _format_amount(amount: float) -> str:
        value = float(amount or 0.0)
        if abs(value - int(value)) < 1e-9:
            return f"{int(value):,}"
        return f"{value:,.2f}"

    @staticmethod
    def _friendly_time(timestamp: str) -> str:
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

    @staticmethod
    def _parse_metadata(tx: dict) -> dict:
        raw_metadata = tx.get("metadata_json")
        if isinstance(raw_metadata, dict):
            return raw_metadata
        return {}

    def _friendly_title(self, tx: dict) -> str:
        tx_type = str(tx.get("type", "") or "").strip().lower()
        metadata = self._parse_metadata(tx)

        if tx_type == "transfer":
            direction = str(metadata.get("direction", "") or "").strip().lower()
            amount = float(tx.get("amount", 0.0) or 0.0)
            return "Transfer Received" if direction == "receive" or amount >= 0 else "Funds Transfer"

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

    @staticmethod
    def _demo_transactions() -> list[dict]:
        now = datetime.now(timezone.utc).isoformat()
        return [
            {"type": "agent_deposit", "amount": 1000.0, "timestamp": now},
            {"type": "transfer", "amount": -200.0, "timestamp": now},
        ]

    def _build_recent_item(self, tx: dict) -> MDCard:
        amount = float(tx.get("amount", 0.0) or 0.0)
        positive = amount >= 0
        sign = "+" if positive else "-"
        layout_scale = float(self.layout_scale or 1.0)
        text_scale = float(self.text_scale or 1.0)
        icon_scale = float(self.icon_scale or 1.0)
        icon_name = "arrow-top-right" if positive else "arrow-bottom-right"
        icon_color = POSITIVE_COLOR if positive else NEGATIVE_COLOR
        icon_bg = [0.22, 0.34, 0.24, 0.96] if positive else [0.33, 0.18, 0.15, 0.96]
        icon_line = [0.50, 0.74, 0.57, 0.34] if positive else [0.86, 0.47, 0.39, 0.28]

        card = MDCard(
            size_hint_y=None,
            height=dp(84 * layout_scale),
            radius=[dp(16 * layout_scale)],
            md_bg_color=TX_CARD_BG,
            padding=[dp(10 * layout_scale), dp(10 * layout_scale), dp(12 * layout_scale), dp(10 * layout_scale)],
            line_color=[0.22, 0.24, 0.28, 0.60],
            elevation=0,
        )

        row = MDBoxLayout(orientation="horizontal", spacing=dp(10 * layout_scale))

        icon_wrap = MDCard(
            size_hint=(None, None),
            size=(dp(44 * layout_scale), dp(44 * layout_scale)),
            radius=[dp(12 * layout_scale)],
            md_bg_color=icon_bg,
            line_color=icon_line,
            elevation=0,
        )
        icon_wrap.add_widget(
            MDIconButton(
                icon=icon_name,
                pos_hint={"center_x": 0.5, "center_y": 0.5},
                size_hint=(None, None),
                size=(dp(22 * layout_scale), dp(22 * layout_scale)),
                theme_text_color="Custom",
                text_color=icon_color,
                user_font_size=f"{20 * icon_scale:.1f}sp",
                disabled=True,
            )
        )

        text_col = MDBoxLayout(orientation="vertical", spacing=dp(2 * layout_scale))
        text_col.add_widget(
            MDLabel(
                text=self._friendly_title(tx),
                font_name=FONT_SEMIBOLD,
                font_size=sp(15 * text_scale),
                bold=True,
                theme_text_color="Custom",
                text_color=[0.95, 0.94, 0.90, 1],
                shorten=True,
                shorten_from="right",
            )
        )
        text_col.add_widget(
            MDLabel(
                text=self._friendly_time(str(tx.get("timestamp", "") or "")),
                font_name=FONT_REGULAR,
                font_size=sp(11 * text_scale),
                theme_text_color="Custom",
                text_color=[0.72, 0.72, 0.74, 1],
            )
        )

        amount_label = MDLabel(
            text=f"{sign} GHS {self._format_amount(abs(amount))}",
            size_hint_x=None,
            width=dp(128 * layout_scale),
            halign="right",
            valign="middle",
            font_name=FONT_SEMIBOLD,
            font_size=sp(15 * text_scale),
            bold=True,
            theme_text_color="Custom",
            text_color=icon_color,
        )

        row.add_widget(icon_wrap)
        row.add_widget(text_col)
        row.add_widget(amount_label)
        card.add_widget(row)
        return card

    def _render_recent_activity(self, rows: list[dict]) -> None:
        container = self.ids.recent_container
        container.clear_widgets()

        for tx in (rows[:2] if rows else self._demo_transactions()):
            container.add_widget(self._build_recent_item(tx))

    def _apply_demo_state(self, greeting_name: str = "") -> None:
        self._set_greeting(greeting_name)
        self.wallet_balance_amount = 5250.0
        self._update_balance_display()
        self.balance_status = "Demo balance"
        self._set_agent_action_state(False)
        self._render_recent_activity([])
        self._refresh_portfolio_values()

    def _extract_first_name(self, payload: dict) -> str:
        if not isinstance(payload, dict):
            return ""
        first_name = str(payload.get("first_name", "") or "").strip()
        if first_name:
            return first_name
        full_name = str(payload.get("full_name", "") or "").strip()
        if full_name:
            return full_name.split()[0]
        return ""

    def _load_home_worker(self, token: str) -> None:
        headers = {"Authorization": f"Bearer {token}"}
        greeting_name = ""
        balance = None
        recent_rows = []
        error_text = ""
        is_agent_active = False
        reset_token = False

        try:
            me_resp = requests.get(f"{API_URL}/auth/me", headers=headers, timeout=10)
            me_payload = me_resp.json() if me_resp.content else {}
            if me_resp.status_code in {401, 403}:
                reset_token = True
            if me_resp.status_code < 400 and isinstance(me_payload, dict):
                greeting_name = self._extract_first_name(me_payload)
        except Exception:
            greeting_name = ""

        if not reset_token:
            try:
                wallet_resp = requests.get(f"{API_URL}/wallet/me", headers=headers, timeout=10)
                wallet_payload = wallet_resp.json() if wallet_resp.content else {}
                if wallet_resp.status_code in {401, 403}:
                    reset_token = True
                elif wallet_resp.status_code < 400 and isinstance(wallet_payload, dict):
                    balance = float(wallet_payload.get("balance", 0.0) or 0.0)
                else:
                    error_text = "Balance unavailable."
            except Exception:
                error_text = "Check connection and try again."

        if not reset_token:
            try:
                tx_resp = requests.get(f"{API_URL}/wallet/transactions/me?limit=2", headers=headers, timeout=10)
                tx_payload = tx_resp.json() if tx_resp.content else []
                if tx_resp.status_code in {401, 403}:
                    reset_token = True
                elif tx_resp.status_code < 400 and isinstance(tx_payload, list):
                    recent_rows = list(tx_payload[:2])
            except Exception:
                if not error_text:
                    error_text = "Activity unavailable."

        if not reset_token:
            try:
                agent_resp = requests.get(f"{API_URL}/agents/me", headers=headers, timeout=10)
                agent_payload = agent_resp.json() if agent_resp.content else {}
                if agent_resp.status_code in {401, 403}:
                    reset_token = True
                elif agent_resp.status_code < 400 and isinstance(agent_payload, dict):
                    status_value = str(agent_payload.get("status", "") or "").strip().lower()
                    is_agent_active = status_value == "active"
            except Exception:
                is_agent_active = False

        Clock.schedule_once(
            lambda _dt: self._apply_home_data(
                greeting_name=greeting_name,
                balance=balance,
                recent_rows=recent_rows,
                error_text=error_text,
                is_agent_active=is_agent_active,
                reset_token=reset_token,
            )
        )

    def _apply_home_data(
        self,
        greeting_name: str = "",
        balance: float | None = None,
        recent_rows: list[dict] | None = None,
        error_text: str = "",
        is_agent_active: bool = False,
        reset_token: bool = False,
    ) -> None:
        self._is_loading = False
        if reset_token:
            app = MDApp.get_running_app()
            app.access_token = ""
            app.pending_momo = ""
            save_token("")
            if self.manager and self.manager.has_screen("login"):
                self.manager.current = "login"
            return
        if greeting_name:
            self._set_greeting(greeting_name)

        if balance is None:
            if self.wallet_balance_amount == 5250.0:
                self.balance_status = error_text or "Demo balance"
        else:
            self.wallet_balance_amount = float(balance)
            self._update_balance_display()
            self.balance_status = "Live balance" if not error_text else error_text

        self._set_agent_action_state(is_agent_active)
        self._render_recent_activity(recent_rows or [])
        self._refresh_portfolio_values()

    def load_home_data(self) -> None:
        if self._is_loading:
            return

        app = MDApp.get_running_app()
        token = str(getattr(app, "access_token", "") or "").strip()
        pending_name = str(getattr(app, "pending_momo", "") or "").strip()

        if pending_name and not pending_name.isdigit():
            self._set_greeting(pending_name)

        if not token:
            self._apply_demo_state(pending_name if not pending_name.isdigit() else "")
            return

        self._is_loading = True
        self.balance_status = "Refreshing..."
        threading.Thread(target=self._load_home_worker, args=(token,), daemon=True).start()

    def open_more_actions(self) -> None:
        tap_feedback()
        content = MoreActionsContent(
            controller=self,
            layout_scale=float(self.layout_scale or 1.0),
            text_scale=float(self.text_scale or 1.0),
            icon_scale=float(self.icon_scale or 1.0),
            compact_mode=bool(self.compact_mode),
            agent_action_label=self.agent_action_label,
            agent_fee_hint=self.agent_action_hint,
        )
        self._more_actions_popup = show_custom_dialog(
            self,
            title="More Actions",
            content_cls=content,
            close_label="Close",
            auto_dismiss=True,
        )

    def close_more_actions(self) -> None:
        dialog = getattr(self, "_more_actions_popup", None) or getattr(self, "_active_dialog", None)
        if dialog:
            try:
                dialog.dismiss()
            except Exception:
                pass
        self._more_actions_popup = None

    def handle_more_action(self, screen_name: str) -> None:
        self.close_more_actions()
        target = str(screen_name or "").strip()
        if not target:
            return
        if target == "agent":
            self._handle_agent_action()
            return
        self.go_to(target)

    def _handle_agent_action(self) -> None:
        if self.is_agent_active:
            self.go_to("agent")
            return
        tap_feedback()
        self._confirm_become_agent()

    @staticmethod
    def _safe_json(response):
        try:
            return response.json() if response.content else {}
        except Exception:
            text = (response.text or "").strip()
            return {"detail": sanitize_backend_message(text or f"HTTP {response.status_code}")}

    @staticmethod
    def _extract_detail(payload: object) -> str:
        return extract_backend_message(payload)

    def _auth_headers(self) -> dict:
        app = MDApp.get_running_app()
        token = str(getattr(app, "access_token", "") or "").strip()
        return {"Authorization": f"Bearer {token}"} if token else {}

    def _confirm_become_agent(self) -> None:
        show_confirm_dialog(
            self,
            title="Become Agent",
            message=(
                f"Pay GHS {AGENT_REGISTRATION_FEE_GHS:,.2f} to become an agent. "
                f"After payment, we activate your Agent Dashboard and add GHS {AGENT_STARTUP_LOAN_GHS:,.2f} startup float."
            ),
            on_confirm=self._initiate_agent_registration,
            confirm_label=f"Pay GHS {AGENT_REGISTRATION_FEE_GHS:,.0f}",
            cancel_label="Cancel",
        )

    def _initiate_agent_registration(self) -> None:
        headers = self._auth_headers()
        if not headers:
            show_message_dialog(
                self,
                title="Sign In Required",
                message="Sign in to register.",
                close_label="Close",
            )
            return

        threading.Thread(
            target=self._initiate_agent_registration_worker,
            args=(headers,),
            daemon=True,
        ).start()

    def _initiate_agent_registration_worker(self, headers: dict) -> None:
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

    def _on_agent_registration_started(self, reference: str, authorization_url: str, message: str) -> None:
        self._last_agent_reference = reference
        friendly_message = (
            message
            or (
                f"Pay GHS {AGENT_REGISTRATION_FEE_GHS:,.2f} with Paystack. "
                f"We'll activate your Agent Dashboard and add GHS {AGENT_STARTUP_LOAN_GHS:,.2f} startup float after payment."
            )
        )
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
                show_message_dialog(
                    self,
                    title="Paystack",
                    message="Checkout couldn't open. Try again.",
                    close_label="Close",
                )

        if reference:
            self._start_agent_registration_verification(reference)

    def _start_agent_registration_verification(self, reference: str) -> None:
        self._agent_verify_sequence += 1
        verify_sequence = self._agent_verify_sequence
        threading.Thread(
            target=self._poll_agent_registration_worker,
            args=(reference, verify_sequence),
            daemon=True,
        ).start()

    def _poll_agent_registration_worker(self, reference: str, verify_sequence: int) -> None:
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

    def _on_agent_registration_success(self, _payload: dict) -> None:
        self._set_agent_action_state(True)
        show_message_dialog(
            self,
            title="Agent Activated",
            message=(
                f"Payment confirmed.\nGHS {AGENT_STARTUP_LOAN_GHS:,.2f} startup float credited."
            ),
            close_label="Open Dashboard",
            on_close=lambda: self.go_to("agent"),
        )
        self.load_home_data()

    def _on_agent_registration_failed(self, detail: str) -> None:
        detail_text = str(detail or "")
        detail_lc = detail_text.lower()
        if "already an active agent" in detail_lc:
            self._set_agent_action_state(True)
            self.go_to("agent")
            return
        if "already an agent" in detail_lc:
            self._verify_existing_agent_status()
            return

        show_message_dialog(
            self,
            title="Registration Failed",
            message=detail_text or "Unable to register right now.",
            close_label="Close",
        )

    def _verify_existing_agent_status(self) -> None:
        headers = self._auth_headers()
        if not headers:
            show_message_dialog(
                self,
                title="Sign In Required",
                message="Sign in again to confirm status.",
                close_label="Close",
            )
            return

        threading.Thread(
            target=self._verify_existing_agent_status_worker,
            args=(headers,),
            daemon=True,
        ).start()

    def _verify_existing_agent_status_worker(self, headers: dict) -> None:
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

        Clock.schedule_once(lambda _dt: self._apply_verified_agent_status(status_value, error_text))

    def _apply_verified_agent_status(self, status_value: str, error_text: str) -> None:
        if status_value == "active":
            self._set_agent_action_state(True)
            self.go_to("agent")
            return

        self._set_agent_action_state(False)
        if status_value == "pending":
            message = "Registration pending. Complete payment to activate."
            title = "Agent Pending"
        elif status_value:
            readable = status_value.replace("_", " ")
            message = f"Status: {readable}. Contact support if needed."
            title = "Agent Status"
        else:
            message = error_text or "Status unavailable."
            title = "Agent Status"

        show_message_dialog(
            self,
            title=title,
            message=message,
            close_label="Close",
        )

    def _on_agent_registration_timeout(self, reference: str) -> None:
        show_message_dialog(
            self,
            title="Still Processing",
            message=(
                "Payment is still processing.\n"
                f"Reference: {reference}\n"
                "Try again shortly."
            ),
            close_label="Close",
        )

    def go_to(self, screen_name: str) -> None:
        if self.manager and self.manager.has_screen(screen_name):
            tap_feedback()
            self.manager.current = screen_name


class MoreActionsContent(MDBoxLayout):
    controller = ObjectProperty()
    layout_scale = NumericProperty(1.0)
    text_scale = NumericProperty(1.0)
    icon_scale = NumericProperty(1.0)
    compact_mode = BooleanProperty(False)
    agent_action_label = StringProperty("Become Agent")
    agent_fee_hint = StringProperty(f"Pay GHS {AGENT_REGISTRATION_FEE_GHS:,.0f}")

    def trigger_action(self, screen_name: str) -> None:
        if self.controller:
            self.controller.handle_more_action(str(screen_name or ""))

Builder.load_string(KV)
