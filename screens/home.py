import os
import json
import threading
import time
import webbrowser
from datetime import datetime, timezone

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.logger import Logger
from kivy.lang import Builder
from kivy.metrics import dp, sp
from kivy.properties import BooleanProperty, ListProperty, NumericProperty, ObjectProperty, StringProperty
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.carousel import Carousel
from kivy.uix.floatlayout import FloatLayout
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDIconButton, MDFloatingActionButton
from kivymd.uix.card import MDCard
from kivymd.uix.fitimage import FitImage
from kivymd.uix.label import MDIcon, MDLabel
from kivymd.uix.refreshlayout import MDScrollViewRefreshLayout

from core.animation_helpers import AnimationManager, DashboardAnimationSequence
from components.balance_counter import BalanceCounter
from components.balance_label import BalanceLabel
from components.pressable_card import PressableCard
from components.wallet_card import WalletCard
from components.transaction_card import TransactionCard
from core.home_assets import home_asset_path
from core.feedback_engine import tap_feedback
from core.fintech_widgets import GradientMDCard
from core.dashboard_state import DashboardState
from core.message_sanitizer import extract_backend_message, sanitize_backend_message
from core.navigation import navigate
from core.paystack_checkout import open_paystack_checkout, warmup_paystack_checkout
from core.popup_manager import show_confirm_dialog, show_custom_dialog, show_message_dialog
from core.responsive_screen import ResponsiveScreen
from core.kivymd_compat import resolve_kivymd_top_app_bar
from features.home.home_controller import HomeController
from services.api import FAST_TIMEOUT, api
from services.market_service import MarketService
from storage import save_token

MDTopAppBar = resolve_kivymd_top_app_bar()


class MDFabButton(MDFloatingActionButton):
    pass

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
            md_bg_color: [0.15, 0.10, 0.10, 0.96]
            line_color: [0.60, 0.30, 0.30, 0.50]
            elevation: 0
            padding: [dp(12 * root.layout_scale)] * 4
            opacity: 1 if app.is_admin else 0.0 # Ensure it's fully hidden when not admin
            disabled: not app.is_admin
            on_release: root.trigger_action("admin_dashboard") # Changed target to admin_dashboard

            MDBoxLayout:
                orientation: "vertical"
                spacing: dp(6 * root.layout_scale)

                MDCard:
                    size_hint: None, None
                    size: dp(44 * root.layout_scale), dp(44 * root.layout_scale)
                    radius: [dp(14 * root.layout_scale)]
                    md_bg_color: [0.30, 0.15, 0.15, 0.98]
                    elevation: 0

                    MDIcon:
                        icon: "shield-account"
                        theme_text_color: "Custom"
                        text_color: [1, 0.6, 0.6, 1]
                        font_size: sp(22 * root.icon_scale)
                        pos_hint: {"center_x": 0.5, "center_y": 0.5}

                MDLabel:
                    text: "Admin Tools"
                    theme_text_color: "Custom"
                    text_color: TEXT_MAIN
                    font_name: FONT_SEMI
                    font_size: sp(14 * root.text_scale)
                    size_hint_y: None
                    height: dp(18 * root.layout_scale)

                MDLabel:
                    text: "System management"
                    theme_text_color: "Custom"
                    text_color: [0.72, 0.75, 0.78, 1]
                    font_name: FONT_REGULAR
                    font_size: sp(11 * root.text_scale)
                    size_hint_y: None
                    height: dp(14 * root.layout_scale)

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
                rgba: (0.42, 0.32, 0.14, 0.10) if app.theme_mode == "Dark" else (0.42, 0.32, 0.14, 0.05)
            Ellipse:
                pos: self.x + self.width * 0.16, self.y + self.height * 0.74
                size: self.width * 0.66, self.width * 0.66
            Color:
                rgba: (0.25, 0.39, 0.32, 0.16) if app.theme_mode == "Dark" else (0.25, 0.39, 0.32, 0.08)
            Ellipse:
                pos: self.x + self.width * 0.38, self.y + self.height * 0.16
                size: self.width * 0.62, self.width * 0.62

        MDTopAppBar:
            title: "CYBER CASH"
            anchor_title: "left"
            elevation: 0
            md_bg_color: app.ui_background
            specific_text_color: app.gold
            left_action_items: [["menu", lambda x: root.open_more_actions()]]
            right_action_items: [["bell-outline", lambda x: root.go_to("transactions")], ["cog-outline", lambda x: root.go_to("settings")]]

        MDScrollViewRefreshLayout:
            id: refresh_layout
            root_layout: app.root
            refresh_callback: root.refresh_dashboard
            spinner_color: app.gold
            circle_color: app.ui_background
            do_scroll_x: False
            bar_width: 0

            MDBoxLayout:
                orientation: "vertical"
                size_hint_y: None
                height: self.minimum_height
                size_hint_x: None
                width: min((self.parent.width if self.parent else root.width), dp(760))
                pos_hint: {"center_x": 0.5}
                padding: [dp(16 * root.layout_scale), dp(14 * root.layout_scale), dp(16 * root.layout_scale), dp(16 * root.layout_scale)]
                spacing: dp(11 * root.layout_scale)

                MDBoxLayout:
                    size_hint_y: None
                    height: dp(72 * root.layout_scale)

                    MDCard:
                        size_hint: None, None
                        size: dp(52 * root.layout_scale), dp(52 * root.layout_scale)
                        radius: [dp(26 * root.layout_scale)]
                        md_bg_color: [0.10, 0.11, 0.14, 0.86]
                        line_color: [0.48, 0.40, 0.26, 0.28]
                        elevation: 0
                        padding: 0
                        pos_hint: {"center_y": 0.5}
                        on_release: root.go_to("settings")

                        FitImage:
                            source: root.avatar_source
                            size_hint: None, None
                            size: dp(40 * root.layout_scale), dp(40 * root.layout_scale)
                            radius: [dp(20 * root.layout_scale)]
                            pos_hint: {"center_x": 0.5, "center_y": 0.5}

                    MDBoxLayout:
                        orientation: "vertical"
                        spacing: dp(1 * root.layout_scale)
                        size_hint_y: None
                        height: dp(42 * root.layout_scale)

                        MDLabel:
                            text: root.time_of_day_text
                            halign: "center"
                            theme_text_color: "Custom"
                            text_color: app.ui_text_secondary
                            font_name: FONT_SEMI
                            font_size: sp(11 * root.text_scale)
                            size_hint_y: None
                            height: dp(14 * root.layout_scale)

                        MDLabel:
                            text: root.greeting_text
                            halign: "center"
                            theme_text_color: "Custom"
                            text_color: app.gold
                            font_name: FONT_BOLD
                            font_style: "Title"
                            font_size: sp(20 * root.text_scale)
                            bold: True

                    FloatLayout:
                        size_hint: None, None
                        size: dp(100 * root.layout_scale), dp(54 * root.layout_scale)

                        MDCard:
                            size_hint: None, None
                            size: dp(44 * root.layout_scale), dp(44 * root.layout_scale)
                            radius: [dp(14 * root.layout_scale)]
                            md_bg_color: [0.10, 0.11, 0.14, 0.74]
                            line_color: [0.48, 0.40, 0.26, 0.24]
                            elevation: 0
                            padding: 0
                            pos_hint: {"center_x": 0.25, "center_y": 0.5}
                            on_release: root.toggle_theme()

                            MDIcon:
                                id: theme_toggle_button
                                icon: root.theme_toggle_icon
                                size_hint: None, None
                                size: dp(28 * root.layout_scale), dp(28 * root.layout_scale)
                                font_size: sp(23 * root.icon_scale)
                                text_size: self.size
                                halign: "center"
                                valign: "center"
                                pos_hint: {"center_x": 0.5, "center_y": 0.5}
                                theme_text_color: "Custom"
                                text_color: app.ui_text_primary

                        MDCard:
                            size_hint: None, None
                            size: dp(44 * root.layout_scale), dp(44 * root.layout_scale)
                            radius: [dp(14 * root.layout_scale)]
                            md_bg_color: [0.10, 0.11, 0.14, 0.74]
                            line_color: [0.48, 0.40, 0.26, 0.24]
                            elevation: 0
                            padding: 0
                            pos_hint: {"center_x": 0.75, "center_y": 0.5}
                            on_release: root.go_to("transactions")

                            MDIcon:
                                icon: "bell-ring-outline"
                                size_hint: None, None
                                size: dp(28 * root.layout_scale), dp(28 * root.layout_scale)
                                font_size: sp(24 * root.icon_scale)
                                text_size: self.size
                                halign: "center"
                                valign: "center"
                                pos_hint: {"center_x": 0.5, "center_y": 0.5}
                                theme_text_color: "Custom"
                                text_color: app.gold

                        MDCard:
                            size_hint: None, None
                            size: dp(18 * root.layout_scale), dp(18 * root.layout_scale)
                            radius: [dp(9 * root.layout_scale)]
                            md_bg_color: [0.85, 0.15, 0.12, 0.98]
                            pos_hint: {"center_x": 0.93, "center_y": 0.78}
                            elevation: 0
                            opacity: 1 if root.notification_badge_visible else 0

                            MDLabel:
                                text: root.notification_count_text
                                halign: "center"
                                valign: "center"
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

                MDCard:
                    size_hint_y: None
                    height: dp(52 * root.layout_scale)
                    radius: [dp(14 * root.layout_scale)]
                    md_bg_color: app.ui_surface
                    line_color: app.ui_glass_border
                    elevation: 0
                    padding: [dp(10 * root.layout_scale), dp(6 * root.layout_scale), dp(12 * root.layout_scale), dp(6 * root.layout_scale)]

                    MDBoxLayout:
                        spacing: dp(8 * root.layout_scale)

                        MDCard:
                            size_hint: None, None
                            size: dp(34 * root.layout_scale), dp(34 * root.layout_scale)
                            radius: [dp(11 * root.layout_scale)]
                            md_bg_color: [0.64, 0.49, 0.20, 0.42]
                            elevation: 0
                            padding: 0

                            MDIcon:
                                icon: "card-account-details-outline"
                                theme_text_color: "Custom"
                                text_color: GOLD
                                font_size: sp(19 * root.icon_scale)
                                size_hint: None, None
                                size: dp(24 * root.layout_scale), dp(24 * root.layout_scale)
                                pos_hint: {"center_x": 0.5, "center_y": 0.5}

                        MDLabel:
                            text: root.greeting_text
                            theme_text_color: "Custom"
                            text_color: app.ui_text_primary
                            font_name: FONT_SEMI
                            font_style: "Body"
                            font_size: sp(16 * root.text_scale)
                            valign: "middle"
                            shorten: True
                            shorten_from: "right"

                        Widget:

                        MDCard:
                            size_hint: None, None
                            size: dp(92 * root.layout_scale), dp(26 * root.layout_scale)
                            radius: [dp(13 * root.layout_scale)]
                            md_bg_color: root.account_status_bg_color
                            elevation: 0

                            MDLabel:
                                text: root.account_status_display
                                halign: "center"
                                valign: "center"
                                theme_text_color: "Custom"
                                text_color: root.account_status_text_color
                                font_size: sp(11.5 * root.text_scale)
                                bold: True

                MDBoxLayout:
                    id: wallet_hero_block
                    opacity: 0
                    orientation: "vertical"
                    size_hint_y: None
                    height: dp(242 * root.layout_scale)
                    spacing: dp(8 * root.layout_scale)

                    MDBoxLayout:
                        size_hint_y: None
                        height: dp(24 * root.layout_scale)

                        MDLabel:
                            text: "Wallet Hero"
                            theme_text_color: "Custom"
                            text_color: app.gold
                            font_name: FONT_BOLD
                            font_size: sp(15 * root.text_scale)
                            bold: True
                            size_hint_x: 1

                        MDCard:
                            size_hint: None, None
                            size: dp(36 * root.layout_scale), dp(22 * root.layout_scale)
                            radius: [dp(7 * root.layout_scale)]
                            md_bg_color: [0, 0, 0, 0]
                            line_color: [0.48, 0.40, 0.26, 0.28]
                            elevation: 0
                            padding: 0

                            MDBoxLayout:
                                orientation: "vertical"
                                spacing: 0

                                Widget:
                                    size_hint_y: 0.34
                                    canvas.before:
                                        Color:
                                            rgba: 0.86, 0.12, 0.12, 1
                                        Rectangle:
                                            pos: self.pos
                                            size: self.size

                                AnchorLayout:
                                    anchor_x: "center"
                                    anchor_y: "center"
                                    size_hint_y: 0.32
                                    canvas.before:
                                        Color:
                                            rgba: 0.95, 0.81, 0.20, 1
                                        Rectangle:
                                            pos: self.pos
                                            size: self.size

                                    MDIcon:
                                        icon: "star"
                                        theme_text_color: "Custom"
                                        text_color: [0.05, 0.05, 0.05, 1]
                                        font_size: sp(10 * root.icon_scale)
                                        pos_hint: {"center_x": 0.5, "center_y": 0.5}

                                Widget:
                                    size_hint_y: 0.34
                                    canvas.before:
                                        Color:
                                            rgba: 0.12, 0.52, 0.22, 1
                                        Rectangle:
                                            pos: self.pos
                                            size: self.size

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
                    id: quick_actions_block
                    opacity: 0
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
                            adaptive_height: True
                            pos_hint: {"center_y": 0.5}

                            MDCard:
                                size_hint: None, None
                                size: dp(38 * root.layout_scale), dp(38 * root.layout_scale)
                                pos_hint: {"center_y": 0.5}
                                radius: [dp(11 * root.layout_scale)]
                                md_bg_color: [0.58, 0.40, 0.15, 0.58]
                                elevation: 0
                                padding: 0

                                MDIcon:
                                    icon: "plus"
                                    theme_text_color: "Custom"
                                    text_color: [0.16, 0.12, 0.07, 1]
                                    font_size: sp(20 * root.icon_scale)
                                    size_hint: None, None
                                    size: dp(25 * root.layout_scale), dp(25 * root.layout_scale)
                                    pos_hint: {"center_x": 0.5, "center_y": 0.5}

                            MDLabel:
                                text: "+ Add Money"
                                theme_text_color: "Custom"
                                text_color: [0, 0, 0, 1]
                                font_name: FONT_BOLD
                                font_size: sp(16 * root.text_scale)
                                valign: "middle"
                                pos_hint: {"center_y": 0.5}
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
                            adaptive_height: True
                            pos_hint: {"center_y": 0.5}

                            MDCard:
                                size_hint: None, None
                                size: dp(38 * root.layout_scale), dp(38 * root.layout_scale)
                                pos_hint: {"center_y": 0.5}
                                radius: [dp(11 * root.layout_scale)]
                                md_bg_color: [0.10, 0.24, 0.19, 0.84]
                                elevation: 0
                                padding: 0

                                MDIcon:
                                    icon: "arrow-top-right"
                                    theme_text_color: "Custom"
                                    text_color: [0.78, 0.93, 0.76, 1]
                                    font_size: sp(20 * root.icon_scale)
                                    size_hint: None, None
                                    size: dp(25 * root.layout_scale), dp(25 * root.layout_scale)
                                    pos_hint: {"center_x": 0.5, "center_y": 0.5}

                            MDLabel:
                                text: "Withdraw"
                                theme_text_color: "Custom"
                                text_color: [0.96, 0.94, 0.88, 1]
                                font_name: FONT_BOLD
                                font_size: sp(17 * root.text_scale)
                                valign: "middle"
                                pos_hint: {"center_y": 0.5}
                                bold: True

                MDBoxLayout:
                    id: promotions_block
                    opacity: 0
                    adaptive_height: True

                    MDLabel:
                        text: "Quick Actions"
                        theme_text_color: "Custom"
                        text_color: app.gold
                        font_name: FONT_BOLD
                        font_size: sp(20 * root.text_scale)

                    MDTextButton:
                        text: "More"
                        theme_text_color: "Custom"
                        text_color: app.gold
                        font_name: FONT_SEMI
                        font_size: sp(15 * root.text_scale)
                        on_release: root.open_more_actions()

                MDGridLayout:
                    cols: 3 if root.width < dp(700) else 6
                    adaptive_height: True
                    row_default_height: dp(114 * root.layout_scale)
                    row_force_default: True
                    spacing: dp(10 * root.layout_scale)

                    MDCard:
                        radius: [dp(24 * root.layout_scale)]
                        md_bg_color: [0.10, 0.13, 0.17, 0.92]
                        line_color: [0.30, 0.48, 0.40, 0.38]
                        elevation: 0
                        padding: [dp(8 * root.layout_scale)] * 4
                        on_release: root.go_to("p2p_transfer")

                        MDBoxLayout:
                            orientation: "vertical"
                            spacing: dp(6 * root.layout_scale)
                            adaptive_height: True

                            AnchorLayout:
                                anchor_x: "center"
                                anchor_y: "center"
                                size_hint_y: None
                                height: dp(52 * root.layout_scale)

                                MDCard:
                                    size_hint: None, None
                                    size: dp(58 * root.layout_scale), dp(58 * root.layout_scale)
                                    radius: [dp(29 * root.layout_scale)]
                                    md_bg_color: [0.18, 0.31, 0.27, 0.96]
                                    elevation: 0

                                    MDIcon:
                                        icon: "send"
                                        theme_text_color: "Custom"
                                        text_color: [0.60, 0.88, 0.72, 1]
                                        font_size: sp(24 * root.icon_scale)
                                        pos_hint: {"center_x": 0.5, "center_y": 0.5}

                            MDLabel:
                                text: "Send Money"
                                halign: "center"
                                theme_text_color: "Custom"
                                text_color: TEXT_MAIN
                                font_name: FONT_SEMI
                                font_size: sp(12 * root.text_scale)

                    MDCard:
                        radius: [dp(24 * root.layout_scale)]
                        md_bg_color: [0.10, 0.13, 0.17, 0.92]
                        line_color: [0.35, 0.50, 0.42, 0.38]
                        elevation: 0
                        padding: [dp(8 * root.layout_scale)] * 4
                        on_release: root.go_to("airtime")

                        MDBoxLayout:
                            orientation: "vertical"
                            spacing: dp(6 * root.layout_scale)
                            adaptive_height: True

                            AnchorLayout:
                                anchor_x: "center"
                                anchor_y: "center"
                                size_hint_y: None
                                height: dp(52 * root.layout_scale)

                                MDCard:
                                    size_hint: None, None
                                    size: dp(58 * root.layout_scale), dp(58 * root.layout_scale)
                                    radius: [dp(29 * root.layout_scale)]
                                    md_bg_color: [0.20, 0.30, 0.18, 0.96]
                                    elevation: 0

                                    MDIcon:
                                        icon: "cellphone"
                                        theme_text_color: "Custom"
                                        text_color: [0.95, 0.80, 0.47, 1]
                                        font_size: sp(24 * root.icon_scale)
                                        pos_hint: {"center_x": 0.5, "center_y": 0.5}

                            MDLabel:
                                text: "Buy Airtime"
                                halign: "center"
                                theme_text_color: "Custom"
                                text_color: TEXT_MAIN
                                font_name: FONT_SEMI
                                font_size: sp(12 * root.text_scale)

                    MDCard:
                        radius: [dp(24 * root.layout_scale)]
                        md_bg_color: [0.10, 0.13, 0.17, 0.92]
                        line_color: [0.33, 0.48, 0.40, 0.38]
                        elevation: 0
                        padding: [dp(8 * root.layout_scale)] * 4
                        on_release: root.go_to("data_bundle")

                        MDBoxLayout:
                            orientation: "vertical"
                            spacing: dp(6 * root.layout_scale)
                            adaptive_height: True

                            AnchorLayout:
                                anchor_x: "center"
                                anchor_y: "center"
                                size_hint_y: None
                                height: dp(52 * root.layout_scale)

                                MDCard:
                                    size_hint: None, None
                                    size: dp(58 * root.layout_scale), dp(58 * root.layout_scale)
                                    radius: [dp(29 * root.layout_scale)]
                                    md_bg_color: [0.20, 0.18, 0.12, 0.96]
                                    elevation: 0

                                    MDIcon:
                                        icon: "sim"
                                        theme_text_color: "Custom"
                                        text_color: [0.95, 0.80, 0.47, 1]
                                        font_size: sp(24 * root.icon_scale)
                                        pos_hint: {"center_x": 0.5, "center_y": 0.5}

                            MDLabel:
                                text: "Buy Data"
                                halign: "center"
                                theme_text_color: "Custom"
                                text_color: TEXT_MAIN
                                font_name: FONT_SEMI
                                font_size: sp(12 * root.text_scale)

                    MDCard:
                        radius: [dp(24 * root.layout_scale)]
                        md_bg_color: [0.10, 0.13, 0.17, 0.92]
                        line_color: [0.42, 0.40, 0.26, 0.38]
                        elevation: 0
                        padding: [dp(8 * root.layout_scale)] * 4
                        on_release: root.go_to("pay_bills")

                        MDBoxLayout:
                            orientation: "vertical"
                            spacing: dp(6 * root.layout_scale)
                            adaptive_height: True

                            AnchorLayout:
                                anchor_x: "center"
                                anchor_y: "center"
                                size_hint_y: None
                                height: dp(52 * root.layout_scale)

                                MDCard:
                                    size_hint: None, None
                                    size: dp(58 * root.layout_scale), dp(58 * root.layout_scale)
                                    radius: [dp(29 * root.layout_scale)]
                                    md_bg_color: [0.24, 0.20, 0.10, 0.96]
                                    elevation: 0

                                    MDIcon:
                                        icon: "receipt-text-outline"
                                        theme_text_color: "Custom"
                                        text_color: [0.95, 0.80, 0.47, 1]
                                        font_size: sp(24 * root.icon_scale)
                                        pos_hint: {"center_x": 0.5, "center_y": 0.5}

                            MDLabel:
                                text: "Pay Bills"
                                halign: "center"
                                theme_text_color: "Custom"
                                text_color: TEXT_MAIN
                                font_name: FONT_SEMI
                                font_size: sp(12 * root.text_scale)

                    MDCard:
                        radius: [dp(24 * root.layout_scale)]
                        md_bg_color: [0.10, 0.13, 0.17, 0.92]
                        line_color: [0.37, 0.38, 0.24, 0.38]
                        elevation: 0
                        padding: [dp(8 * root.layout_scale)] * 4
                        on_release: root.go_to("btc")

                        MDBoxLayout:
                            orientation: "vertical"
                            spacing: dp(6 * root.layout_scale)
                            adaptive_height: True

                            AnchorLayout:
                                anchor_x: "center"
                                anchor_y: "center"
                                size_hint_y: None
                                height: dp(52 * root.layout_scale)

                                MDCard:
                                    size_hint: None, None
                                    size: dp(58 * root.layout_scale), dp(58 * root.layout_scale)
                                    radius: [dp(29 * root.layout_scale)]
                                    md_bg_color: [0.24, 0.18, 0.08, 0.96]
                                    elevation: 0

                                    MDIcon:
                                        icon: "bitcoin"
                                        theme_text_color: "Custom"
                                        text_color: [0.97, 0.68, 0.15, 1]
                                        font_size: sp(24 * root.icon_scale)
                                        pos_hint: {"center_x": 0.5, "center_y": 0.5}

                            MDLabel:
                                text: "Crypto"
                                halign: "center"
                                theme_text_color: "Custom"
                                text_color: TEXT_MAIN
                                font_name: FONT_SEMI
                                font_size: sp(12 * root.text_scale)

                    MDCard:
                        radius: [dp(24 * root.layout_scale)]
                        md_bg_color: [0.10, 0.13, 0.17, 0.92]
                        line_color: [0.40, 0.34, 0.22, 0.38]
                        elevation: 0
                        padding: [dp(8 * root.layout_scale)] * 4
                        on_release: root.open_more_actions()

                        MDBoxLayout:
                            orientation: "vertical"
                            spacing: dp(6 * root.layout_scale)
                            adaptive_height: True

                            AnchorLayout:
                                anchor_x: "center"
                                anchor_y: "center"
                                size_hint_y: None
                                height: dp(52 * root.layout_scale)

                                MDCard:
                                    size_hint: None, None
                                    size: dp(58 * root.layout_scale), dp(58 * root.layout_scale)
                                    radius: [dp(29 * root.layout_scale)]
                                    md_bg_color: [0.25, 0.20, 0.11, 0.96]
                                    elevation: 0

                                    MDIcon:
                                        icon: "view-grid"
                                        theme_text_color: "Custom"
                                        text_color: [0.95, 0.80, 0.47, 1]
                                        font_size: sp(24 * root.icon_scale)
                                        pos_hint: {"center_x": 0.5, "center_y": 0.5}

                            MDLabel:
                                text: "More"
                                halign: "center"
                                theme_text_color: "Custom"
                                text_color: TEXT_MAIN
                                font_name: FONT_SEMI
                                font_size: sp(12 * root.text_scale)

                MDBoxLayout:
                    adaptive_height: True

                    MDLabel:
                        text: "Promotions"
                        theme_text_color: "Custom"
                        text_color: app.gold
                        font_name: FONT_BOLD
                        font_size: sp(20 * root.text_scale)

                    MDTextButton:
                        text: "Join Today"
                        theme_text_color: "Custom"
                        text_color: app.gold
                        font_name: FONT_SEMI
                        font_size: sp(15 * root.text_scale)
                        on_release: root.open_promo_cta("FIRST 50 USERS", "Get free GH¢20. Sponsored by Cyber World Store.")

                GradientMDCard:
                    size_hint_y: None
                    height: dp(176 * root.layout_scale)
                    radius: [dp(24 * root.layout_scale)]
                    gradient_start: [0.12, 0.10, 0.07, 1]
                    gradient_end: [0.04, 0.06, 0.09, 1]
                    border_color: [0.94, 0.79, 0.46, 0.18]
                    border_width: dp(1)
                    padding: [dp(14 * root.layout_scale), dp(14 * root.layout_scale), dp(14 * root.layout_scale), dp(12 * root.layout_scale)]

                    MDBoxLayout:
                        orientation: "vertical"
                        spacing: dp(10 * root.layout_scale)

                        Carousel:
                            id: promo_carousel
                            direction: "right"
                            loop: True
                            anim_move_duration: 0.25
                            on_index: root.promo_index = self.index

                            MDBoxLayout:
                                orientation: "vertical"
                                spacing: dp(4 * root.layout_scale)
                                padding: [dp(4 * root.layout_scale), 0, dp(4 * root.layout_scale), 0]
                                MDLabel:
                                    text: "🎁 FIRST 50 USERS"
                                    theme_text_color: "Custom"
                                    text_color: app.gold
                                    font_name: FONT_BOLD
                                    font_size: sp(14 * root.text_scale)
                                    bold: True
                                MDLabel:
                                    text: "GET FREE GH¢20"
                                    theme_text_color: "Custom"
                                    text_color: TEXT_MAIN
                                    font_name: FONT_BOLD
                                    font_size: sp(26 * root.text_scale)
                                    bold: True
                                MDLabel:
                                    text: "Sponsored by Cyber World Store"
                                    theme_text_color: "Custom"
                                    text_color: app.ui_text_secondary
                                    font_name: FONT_SEMI
                                    font_size: sp(12 * root.text_scale)
                                Widget:
                                MDTextButton:
                                    text: "Join Today"
                                    theme_text_color: "Custom"
                                    text_color: app.gold
                                    font_name: FONT_SEMI
                                    on_release: root.open_promo_cta("First 50 Users", "Join now to claim the GH¢20 launch bonus while it lasts.")

                            MDBoxLayout:
                                orientation: "vertical"
                                spacing: dp(4 * root.layout_scale)
                                padding: [dp(4 * root.layout_scale), 0, dp(4 * root.layout_scale), 0]
                                MDLabel:
                                    text: "Limited launch offer"
                                    theme_text_color: "Custom"
                                    text_color: app.gold
                                    font_name: FONT_BOLD
                                    font_size: sp(14 * root.text_scale)
                                MDLabel:
                                    text: "Join the queue, finish your profile, and unlock premium wallet tools."
                                    theme_text_color: "Custom"
                                    text_color: TEXT_MAIN
                                    font_name: FONT_BOLD
                                    font_size: sp(23 * root.text_scale)
                                    bold: True
                                MDLabel:
                                    text: "Cyber World Store is sponsoring the first wave."
                                    theme_text_color: "Custom"
                                    text_color: app.ui_text_secondary
                                    font_name: FONT_SEMI
                                    font_size: sp(12 * root.text_scale)
                                Widget:
                                MDTextButton:
                                    text: "See Details"
                                    theme_text_color: "Custom"
                                    text_color: app.gold
                                    font_name: FONT_SEMI
                                    on_release: root.open_more_actions()

                            MDBoxLayout:
                                orientation: "vertical"
                                spacing: dp(4 * root.layout_scale)
                                padding: [dp(4 * root.layout_scale), 0, dp(4 * root.layout_scale), 0]
                                MDLabel:
                                    text: "Auto scrolls every 5 seconds"
                                    theme_text_color: "Custom"
                                    text_color: app.gold
                                    font_name: FONT_BOLD
                                    font_size: sp(14 * root.text_scale)
                                MDLabel:
                                    text: "Stay close to the dashboard for live offers, wallet alerts, and new rewards."
                                    theme_text_color: "Custom"
                                    text_color: TEXT_MAIN
                                    font_name: FONT_BOLD
                                    font_size: sp(23 * root.text_scale)
                                    bold: True
                                MDLabel:
                                    text: "Sponsored by Cyber World Store"
                                    theme_text_color: "Custom"
                                    text_color: app.ui_text_secondary
                                    font_name: FONT_SEMI
                                    font_size: sp(12 * root.text_scale)
                                Widget:
                                MDTextButton:
                                    text: "Open Offers"
                                    theme_text_color: "Custom"
                                    text_color: app.gold
                                    font_name: FONT_SEMI
                                    on_release: root.open_more_actions()

                        MDBoxLayout:
                            size_hint_y: None
                            height: dp(10 * root.layout_scale)
                            spacing: dp(6 * root.layout_scale)
                            size_hint_x: None
                            width: dp(44 * root.layout_scale)
                            pos_hint: {"center_x": 0.5}

                            Widget:
                                size_hint: None, None
                                size: dp(8 * root.layout_scale), dp(8 * root.layout_scale)
                                canvas.before:
                                    Color:
                                        rgba: app.gold if root.promo_index == 0 else app.ui_text_secondary
                                    RoundedRectangle:
                                        pos: self.pos
                                        size: self.size
                                        radius: [dp(4 * root.layout_scale)]

                            Widget:
                                size_hint: None, None
                                size: dp(8 * root.layout_scale), dp(8 * root.layout_scale)
                                canvas.before:
                                    Color:
                                        rgba: app.gold if root.promo_index == 1 else app.ui_text_secondary
                                    RoundedRectangle:
                                        pos: self.pos
                                        size: self.size
                                        radius: [dp(4 * root.layout_scale)]

                            Widget:
                                size_hint: None, None
                                size: dp(8 * root.layout_scale), dp(8 * root.layout_scale)
                                canvas.before:
                                    Color:
                                        rgba: app.gold if root.promo_index == 2 else app.ui_text_secondary
                                    RoundedRectangle:
                                        pos: self.pos
                                        size: self.size
                                        radius: [dp(4 * root.layout_scale)]

                MDBoxLayout:
                    adaptive_height: True

                    MDLabel:
                        text: "Services"
                        theme_text_color: "Custom"
                        text_color: app.gold
                        font_name: FONT_BOLD
                        font_size: sp(20 * root.text_scale)

                    MDTextButton:
                        text: "Full List"
                        theme_text_color: "Custom"
                        text_color: app.gold
                        font_name: FONT_SEMI
                        font_size: sp(15 * root.text_scale)
                        on_release: root.open_more_actions()

                MDGridLayout:
                    cols: 2 if root.width < dp(560) else 5
                    adaptive_height: True
                    row_default_height: dp(96 * root.layout_scale)
                    row_force_default: True
                    spacing: dp(10 * root.layout_scale)

                    MDCard:
                        radius: [dp(18 * root.layout_scale)]
                        md_bg_color: [0.09, 0.13, 0.17, 0.92]
                        line_color: [0.30, 0.48, 0.40, 0.38]
                        elevation: 0
                        padding: [dp(10 * root.layout_scale)] * 4
                        on_release: root.go_to("p2p_transfer")
                        MDBoxLayout:
                            orientation: "vertical"
                            spacing: dp(4 * root.layout_scale)
                            MDIcon:
                                icon: "swap-horizontal"
                                theme_text_color: "Custom"
                                text_color: app.gold
                                font_size: sp(22 * root.icon_scale)
                                size_hint_y: None
                                height: dp(26 * root.layout_scale)
                            MDLabel:
                                text: "Transfer"
                                halign: "center"
                                theme_text_color: "Custom"
                                text_color: TEXT_MAIN
                                font_name: FONT_SEMI
                                font_size: sp(12 * root.text_scale)

                    MDCard:
                        radius: [dp(18 * root.layout_scale)]
                        md_bg_color: [0.09, 0.13, 0.17, 0.92]
                        line_color: [0.32, 0.49, 0.42, 0.38]
                        elevation: 0
                        padding: [dp(10 * root.layout_scale)] * 4
                        on_release: root.go_to("withdraw")
                        MDBoxLayout:
                            orientation: "vertical"
                            spacing: dp(4 * root.layout_scale)
                            MDIcon:
                                icon: "cash-minus"
                                theme_text_color: "Custom"
                                text_color: app.gold
                                font_size: sp(22 * root.icon_scale)
                                size_hint_y: None
                                height: dp(26 * root.layout_scale)
                            MDLabel:
                                text: "Withdraw"
                                halign: "center"
                                theme_text_color: "Custom"
                                text_color: TEXT_MAIN
                                font_name: FONT_SEMI
                                font_size: sp(12 * root.text_scale)

                    MDCard:
                        radius: [dp(18 * root.layout_scale)]
                        md_bg_color: [0.09, 0.13, 0.17, 0.92]
                        line_color: [0.30, 0.48, 0.40, 0.38]
                        elevation: 0
                        padding: [dp(10 * root.layout_scale)] * 4
                        on_release: root.go_to("virtual_card")
                        MDBoxLayout:
                            orientation: "vertical"
                            spacing: dp(4 * root.layout_scale)
                            MDIcon:
                                icon: "credit-card-outline"
                                theme_text_color: "Custom"
                                text_color: app.gold
                                font_size: sp(22 * root.icon_scale)
                                size_hint_y: None
                                height: dp(26 * root.layout_scale)
                            MDLabel:
                                text: "Virtual Card"
                                halign: "center"
                                theme_text_color: "Custom"
                                text_color: TEXT_MAIN
                                font_name: FONT_SEMI
                                font_size: sp(12 * root.text_scale)

                    MDCard:
                        radius: [dp(18 * root.layout_scale)]
                        md_bg_color: [0.09, 0.13, 0.17, 0.92]
                        line_color: [0.30, 0.48, 0.40, 0.38]
                        elevation: 0
                        padding: [dp(10 * root.layout_scale)] * 4
                        on_release: root.go_to("airtime_2_cash")
                        MDBoxLayout:
                            orientation: "vertical"
                            spacing: dp(4 * root.layout_scale)
                            MDIcon:
                                icon: "cash-fast"
                                theme_text_color: "Custom"
                                text_color: app.gold
                                font_size: sp(22 * root.icon_scale)
                                size_hint_y: None
                                height: dp(26 * root.layout_scale)
                            MDLabel:
                                text: "Airtime2Cash"
                                halign: "center"
                                theme_text_color: "Custom"
                                text_color: TEXT_MAIN
                                font_name: FONT_SEMI
                                font_size: sp(11.5 * root.text_scale)

                    MDCard:
                        radius: [dp(18 * root.layout_scale)]
                        md_bg_color: [0.09, 0.13, 0.17, 0.92]
                        line_color: [0.30, 0.48, 0.40, 0.38]
                        elevation: 0
                        padding: [dp(10 * root.layout_scale)] * 4
                        on_release: root.go_to("investments")
                        MDBoxLayout:
                            orientation: "vertical"
                            spacing: dp(4 * root.layout_scale)
                            MDIcon:
                                icon: "bank-outline"
                                theme_text_color: "Custom"
                                text_color: app.gold
                                font_size: sp(22 * root.icon_scale)
                                size_hint_y: None
                                height: dp(26 * root.layout_scale)
                            MDLabel:
                                text: "Savings"
                                halign: "center"
                                theme_text_color: "Custom"
                                text_color: TEXT_MAIN
                                font_name: FONT_SEMI
                                font_size: sp(12 * root.text_scale)

                    MDCard:
                        radius: [dp(18 * root.layout_scale)]
                        md_bg_color: [0.09, 0.13, 0.17, 0.92]
                        line_color: [0.30, 0.48, 0.40, 0.38]
                        elevation: 0
                        padding: [dp(10 * root.layout_scale)] * 4
                        on_release: root.go_to("investments")
                        MDBoxLayout:
                            orientation: "vertical"
                            spacing: dp(4 * root.layout_scale)
                            MDIcon:
                                icon: "chart-line"
                                theme_text_color: "Custom"
                                text_color: app.gold
                                font_size: sp(22 * root.icon_scale)
                                size_hint_y: None
                                height: dp(26 * root.layout_scale)
                            MDLabel:
                                text: "Investment"
                                halign: "center"
                                theme_text_color: "Custom"
                                text_color: TEXT_MAIN
                                font_name: FONT_SEMI
                                font_size: sp(12 * root.text_scale)

                    MDCard:
                        radius: [dp(18 * root.layout_scale)]
                        md_bg_color: [0.09, 0.13, 0.17, 0.92]
                        line_color: [0.30, 0.48, 0.40, 0.38]
                        elevation: 0
                        padding: [dp(10 * root.layout_scale)] * 4
                        on_release: root.go_to("loans")
                        MDBoxLayout:
                            orientation: "vertical"
                            spacing: dp(4 * root.layout_scale)
                            MDIcon:
                                icon: "hand-coin"
                                theme_text_color: "Custom"
                                text_color: app.gold
                                font_size: sp(22 * root.icon_scale)
                                size_hint_y: None
                                height: dp(26 * root.layout_scale)
                            MDLabel:
                                text: "Loans"
                                halign: "center"
                                theme_text_color: "Custom"
                                text_color: TEXT_MAIN
                                font_name: FONT_SEMI
                                font_size: sp(12 * root.text_scale)

                    MDCard:
                        radius: [dp(18 * root.layout_scale)]
                        md_bg_color: [0.09, 0.13, 0.17, 0.92]
                        line_color: [0.30, 0.48, 0.40, 0.38]
                        elevation: 0
                        padding: [dp(10 * root.layout_scale)] * 4
                        on_release: root.go_to("escrow")
                        MDBoxLayout:
                            orientation: "vertical"
                            spacing: dp(4 * root.layout_scale)
                            MDIcon:
                                icon: "shield-account-outline"
                                theme_text_color: "Custom"
                                text_color: app.gold
                                font_size: sp(22 * root.icon_scale)
                                size_hint_y: None
                                height: dp(26 * root.layout_scale)
                            MDLabel:
                                text: "Insurance"
                                halign: "center"
                                theme_text_color: "Custom"
                                text_color: TEXT_MAIN
                                font_name: FONT_SEMI
                                font_size: sp(12 * root.text_scale)

                    MDCard:
                        radius: [dp(18 * root.layout_scale)]
                        md_bg_color: [0.09, 0.13, 0.17, 0.92]
                        line_color: [0.30, 0.48, 0.40, 0.38]
                        elevation: 0
                        padding: [dp(10 * root.layout_scale)] * 4
                        on_release: root.open_promo_cta("QR Pay", "QR Pay is coming soon. Use Send Money or Virtual Card for now.")
                        MDBoxLayout:
                            orientation: "vertical"
                            spacing: dp(4 * root.layout_scale)
                            MDIcon:
                                icon: "qrcode-scan"
                                theme_text_color: "Custom"
                                text_color: app.gold
                                font_size: sp(22 * root.icon_scale)
                                size_hint_y: None
                                height: dp(26 * root.layout_scale)
                            MDLabel:
                                text: "QR Pay"
                                halign: "center"
                                theme_text_color: "Custom"
                                text_color: TEXT_MAIN
                                font_name: FONT_SEMI
                                font_size: sp(12 * root.text_scale)

                    MDCard:
                        radius: [dp(18 * root.layout_scale)]
                        md_bg_color: [0.09, 0.13, 0.17, 0.92]
                        line_color: [0.30, 0.48, 0.40, 0.38]
                        elevation: 0
                        padding: [dp(10 * root.layout_scale)] * 4
                        on_release: root.go_to("transactions")
                        MDBoxLayout:
                            orientation: "vertical"
                            spacing: dp(4 * root.layout_scale)
                            MDIcon:
                                icon: "history"
                                theme_text_color: "Custom"
                                text_color: app.gold
                                font_size: sp(22 * root.icon_scale)
                                size_hint_y: None
                                height: dp(26 * root.layout_scale)
                            MDLabel:
                                text: "History"
                                halign: "center"
                                theme_text_color: "Custom"
                                text_color: TEXT_MAIN
                                font_name: FONT_SEMI
                                font_size: sp(12 * root.text_scale)

                GradientMDCard:
                    size_hint_y: None
                    height: dp(170 * root.layout_scale)
                    radius: [dp(22 * root.layout_scale)]
                    gradient_start: [0.07, 0.10, 0.14, 1]
                    gradient_end: [0.04, 0.05, 0.07, 1]
                    border_color: [0.95, 0.80, 0.47, 0.16]
                    border_width: dp(1)
                    padding: [dp(14 * root.layout_scale), dp(14 * root.layout_scale), dp(14 * root.layout_scale), dp(14 * root.layout_scale)]

                    MDBoxLayout:
                        orientation: "vertical"
                        spacing: dp(8 * root.layout_scale)

                        MDBoxLayout:
                            size_hint_y: None
                            height: dp(36 * root.layout_scale)

                            MDLabel:
                                text: "Live Market"
                                theme_text_color: "Custom"
                                text_color: app.gold
                                font_name: FONT_BOLD
                                font_size: sp(18 * root.text_scale)

                            MDCard:
                                size_hint: None, None
                                size: dp(92 * root.layout_scale), dp(26 * root.layout_scale)
                                radius: [dp(13 * root.layout_scale)]
                                md_bg_color: root.market_status_color
                                elevation: 0

                                MDLabel:
                                    text: root.market_status_text
                                    halign: "center"
                                    valign: "center"
                                    theme_text_color: "Custom"
                                    text_color: 1, 1, 1, 1
                                    font_size: sp(10.5 * root.text_scale)
                                    bold: True

                            MDIconButton:
                                icon: "refresh"
                                user_font_size: str(20 * root.icon_scale) + "sp"
                                theme_text_color: "Custom"
                                text_color: app.gold
                                on_release: root.refresh_market_data()

                        MDGridLayout:
                            cols: 2
                            adaptive_height: True
                            spacing: dp(10 * root.layout_scale)

                            MDCard:
                                radius: [dp(18 * root.layout_scale)]
                                md_bg_color: [0.09, 0.11, 0.14, 0.88]
                                line_color: [0.30, 0.48, 0.40, 0.30]
                                elevation: 0
                                padding: [dp(12 * root.layout_scale)] * 4
                                MDBoxLayout:
                                    orientation: "vertical"
                                    spacing: dp(4 * root.layout_scale)
                                    MDLabel:
                                        text: root.market_btc_display
                                        theme_text_color: "Custom"
                                        text_color: app.gold
                                        font_name: FONT_BOLD
                                        font_size: sp(22 * root.text_scale)
                                    MDLabel:
                                        text: root.market_change_display
                                        theme_text_color: "Custom"
                                        text_color: root.market_change_color
                                        font_name: FONT_SEMI
                                        font_size: sp(12 * root.text_scale)
                                    MDLabel:
                                        text: root.market_updated_text
                                        theme_text_color: "Custom"
                                        text_color: app.ui_text_secondary
                                        font_size: sp(11 * root.text_scale)

                            MDCard:
                                radius: [dp(18 * root.layout_scale)]
                                md_bg_color: [0.09, 0.11, 0.14, 0.88]
                                line_color: [0.30, 0.48, 0.40, 0.30]
                                elevation: 0
                                padding: [dp(12 * root.layout_scale)] * 4
                                MDBoxLayout:
                                    orientation: "vertical"
                                    spacing: dp(4 * root.layout_scale)
                                    MDLabel:
                                        text: root.market_fx_display
                                        theme_text_color: "Custom"
                                        text_color: app.gold
                                        font_name: FONT_BOLD
                                        font_size: sp(22 * root.text_scale)
                                    MDLabel:
                                        text: "Auto-updates from the live feed."
                                        theme_text_color: "Custom"
                                        text_color: app.ui_text_secondary
                                        font_size: sp(11 * root.text_scale)
                                    MDLabel:
                                        text: "Swipe the hero card for the full market view."
                                        theme_text_color: "Custom"
                                        text_color: app.ui_text_secondary
                                        font_size: sp(11 * root.text_scale)

                GradientMDCard:
                    size_hint_y: None
                    height: dp(132 * root.layout_scale)
                    radius: [dp(22 * root.layout_scale)]
                    gradient_start: [0.14, 0.10, 0.07, 1]
                    gradient_end: [0.05, 0.07, 0.10, 1]
                    border_color: [0.94, 0.79, 0.46, 0.15]
                    border_width: dp(1)
                    padding: [dp(12 * root.layout_scale), dp(12 * root.layout_scale), dp(12 * root.layout_scale), dp(12 * root.layout_scale)]
                    on_release: root.open_promo_cta("GHANA CUP FINAL", "Predict & Win is a limited-time campaign. Join the conversation and stay ready.")

                    MDBoxLayout:
                        spacing: dp(10 * root.layout_scale)
                        AnchorLayout:
                            anchor_x: "center"
                            anchor_y: "center"
                            size_hint_x: None
                            width: dp(54 * root.layout_scale)
                            MDCard:
                                size_hint: None, None
                                size: dp(54 * root.layout_scale), dp(54 * root.layout_scale)
                                radius: [dp(27 * root.layout_scale)]
                                md_bg_color: [0.25, 0.20, 0.11, 0.96]
                                elevation: 0
                                MDIcon:
                                    icon: "trophy"
                                    theme_text_color: "Custom"
                                    text_color: app.gold
                                    font_size: sp(26 * root.icon_scale)
                                    pos_hint: {"center_x": 0.5, "center_y": 0.5}

                        MDBoxLayout:
                            orientation: "vertical"
                            spacing: dp(2 * root.layout_scale)
                            adaptive_height: True

                            MDLabel:
                                text: "GHANA CUP FINAL"
                                theme_text_color: "Custom"
                                text_color: app.gold
                                font_name: FONT_BOLD
                                font_size: sp(14 * root.text_scale)
                            MDLabel:
                                text: "Predict & Win"
                                theme_text_color: "Custom"
                                text_color: TEXT_MAIN
                                font_name: FONT_BOLD
                                font_size: sp(20 * root.text_scale)
                            MDLabel:
                                text: "Sponsored by Cyber World Store"
                                theme_text_color: "Custom"
                                text_color: app.ui_text_secondary
                                font_name: FONT_SEMI
                                font_size: sp(11.5 * root.text_scale)

                        Widget:

                        MDTextButton:
                            text: "Join Now"
                            theme_text_color: "Custom"
                            text_color: app.gold
                            font_name: FONT_SEMI
                            font_size: sp(14 * root.text_scale)
                            on_release: root.open_promo_cta("GHANA CUP FINAL", "Predict & Win is open to the community. Join now for promo details.")

                MDBoxLayout:
                    adaptive_height: True

                    MDLabel:
                        text: "Recent Transactions"
                        theme_text_color: "Custom"
                        text_color: app.ui_text_primary
                        font_name: FONT_BOLD
                        font_size: sp(20 * root.text_scale)

                    MDBoxLayout:
                        size_hint_x: None
                        width: dp(118 * root.layout_scale)
                        spacing: dp(2 * root.layout_scale)
                        adaptive_height: True

                        MDIconButton:
                            icon: "magnify"
                            user_font_size: str(20 * root.icon_scale) + "sp"
                            theme_text_color: "Custom"
                            text_color: app.ui_text_secondary
                            on_release: root.go_to("transactions")

                        MDIconButton:
                            icon: "filter-variant"
                            user_font_size: str(20 * root.icon_scale) + "sp"
                            theme_text_color: "Custom"
                            text_color: app.ui_text_secondary
                            on_release: root.open_more_actions()

                        MDTextButton:
                            text: "See All"
                            theme_text_color: "Custom"
                            text_color: app.gold
                            font_name: FONT_SEMI
                            font_size: sp(14 * root.text_scale)
                            on_release: root.go_to("transactions")

                MDLabel:
                    text: "Today"
                    theme_text_color: "Custom"
                    text_color: app.ui_text_secondary
                    font_name: FONT_SEMI
                    font_size: sp(12 * root.text_scale)
                    size_hint_y: None
                    height: dp(18 * root.layout_scale)

                MDBoxLayout:
                    id: recent_container
                    opacity: 0
                    orientation: "vertical"
                    adaptive_height: True
                    spacing: dp(10 * root.layout_scale)

                Widget:
                    size_hint_y: None
                    height: dp(14 * root.layout_scale)

        MDFabButton:
            icon: "help-circle-outline"
            md_bg_color: app.gold
            size_hint: None, None
            size: dp(56 * root.layout_scale), dp(56 * root.layout_scale)
            pos_hint: {"right": 0.96, "y": 0.12}
            on_release: root.open_dashboard_help()

        BottomNavBar:
            id: bottom_navigation
            opacity: 0
            nav_variant: "dashboard"
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
    brand_logo_source = StringProperty("")
    hero_art_source = StringProperty("")
    greeting_text = StringProperty("Welcome back")
    time_of_day_text = StringProperty("Good evening")
    notification_count_text = StringProperty("0")
    notification_badge_visible = BooleanProperty(False)
    portfolio_index = NumericProperty(0)
    promo_index = NumericProperty(0)
    theme_toggle_icon = StringProperty("weather-night")
    wallet_balance_amount = NumericProperty(0.0)
    wallet_balance_loaded = BooleanProperty(False)
    balance_placeholder = StringProperty("Syncing...")
    balance_hidden = BooleanProperty(False)
    balance_display = StringProperty("Syncing...")
    available_balance_display = StringProperty("Syncing...")
    bonus_balance_display = StringProperty("GH¢ 0.00")
    balance_status = StringProperty("Waiting for live wallet")
    account_status_display = StringProperty("SYNC")
    account_status_bg_color = ListProperty([0.12, 0.14, 0.18, 0.95])
    account_status_text_color = ListProperty([0.86, 0.88, 0.90, 1])
    market_btc_display = StringProperty("BTC $0.00")
    market_fx_display = StringProperty("USD/GHS 0.00")
    market_change_display = StringProperty("+0.0% 24h")
    market_change_color = ListProperty([0.54, 0.82, 0.67, 1])
    market_change_icon = StringProperty("trending-up")
    market_status_text = StringProperty("MARKET LIVE")
    market_status_color = ListProperty([0.54, 0.82, 0.67, 1])
    market_updated_text = StringProperty("Updating...")
    loading_skeleton_visible = BooleanProperty(False)
    offline_banner_visible = BooleanProperty(False)
    offline_banner_text = StringProperty("Offline mode")
    is_agent_active = BooleanProperty(False)
    dashboard_ready = BooleanProperty(False)
    agent_action_label = StringProperty("Become Agent")
    agent_action_hint = StringProperty(f"Pay GH¢ {AGENT_REGISTRATION_FEE_GHS:,.0f}")
    _loading = False
    _is_loading = False

    def __init__(self, **kwargs):
        self._more_actions_popup = None
        self._agent_verify_sequence = 0
        self._last_agent_reference = ""
        self._portfolio_carousel_ready = False
        self._portfolio_cards: dict[str, dict[str, object]] = {}
        self._recent_rows_pending: list[dict] | None = None
        self._recent_render_sequence = 0
        self._home_kv_ready = False
        self._promo_scroll_event = None
        self._market_refresh_event = None
        self._dashboard_refresh_event = None
        self._market_loading = False
        self._market_load_seq = 0
        self._market_snapshot: dict | None = None
        self._dashboard_load_seq = 0
        self._dashboard_events_bound = False
        self._home_entrance_played = False
        self.dashboard_state = DashboardState()
        self.home_controller = HomeController()
        self.home_controller.state = self.dashboard_state
        self.market_service = MarketService()
        super().__init__(**kwargs)
        self.avatar_source = self._resolve_avatar_source()
        self.background_source = self._resolve_asset_source(
            home_asset_path("03_wallet_hero/wallet_world_map.png"),
            "kivy_frontend/assets/background.png",
        )
        self.brand_logo_source = self._resolve_asset_source(
            home_asset_path("01_branding/cyber_cash_shield_logo.png"),
            home_asset_path("01_branding/cyber_cash_wordmark.png"),
            "assets/cybercash_logo.png",
            "assets/cybercash_icon.png",
        )
        self.hero_art_source = self._resolve_asset_source(
            home_asset_path("10_ui_composites/wallet_card_composite.png"),
            home_asset_path("03_wallet_hero/wallet_shield.png"),
            "assets/cybercash_icon.png",
            "assets/cybercash_logo.png",
        )
        self._update_balance_display()

    def on_kv_post(self, _base_widget):
        super().on_kv_post(_base_widget)
        self._home_kv_ready = True
        Clock.schedule_once(lambda _dt: self._prime_premium_ui(), 0.05)
        self._ensure_dashboard_timers()
        if self._recent_rows_pending is not None:
            Clock.schedule_once(lambda _dt: self._render_recent_activity(self._recent_rows_pending or []), 0.05)

    def on_pre_enter(self):
        self._sync_theme_toggle_icon()
        self.show_loading_state()
        self._bind_dashboard_events()
        Clock.schedule_once(lambda _dt: self._ensure_dashboard_timers(), 0.02)

    def on_enter(self):
        Clock.schedule_once(lambda _dt: self.start_entrance_animation(), 0.05)
        Clock.schedule_once(lambda _dt: self.load_dashboard(), 0.08)
        Clock.schedule_once(lambda _dt: self.refresh_market_data(silent=True), 0.15)

    def on_leave(self, *_args):
        self._agent_verify_sequence += 1
        self.stop_background_tasks()
        self._unbind_dashboard_events()
        self.close_more_actions()

    def show_loading_state(self) -> None:
        self.loading_skeleton_visible = True
        self.offline_banner_visible = False
        self.notification_badge_visible = False
        self.notification_count_text = "0"
        self.dashboard_ready = False
        self._home_entrance_played = False
        self._set_account_status("SYNC", [0.12, 0.14, 0.18, 0.95], [0.86, 0.88, 0.90, 1])
        self.balance_status = "Loading dashboard..."
        if not self.wallet_balance_loaded:
            self.balance_placeholder = "Loading..."
            self._update_balance_display()
        self._refresh_portfolio_values()

    def start_entrance_animation(self) -> None:
        if not self._home_kv_ready:
            Clock.schedule_once(lambda _dt: self.start_entrance_animation(), 0.05)
            return
        if not self.manager or self.manager.current != self.name:
            return
        if self.loading_skeleton_visible and not self.dashboard_ready:
            Clock.schedule_once(lambda _dt: self.start_entrance_animation(), 0.08)
            return
        if getattr(self, "_home_entrance_played", False):
            return
        if not self.dashboard_ready:
            Clock.schedule_once(lambda _dt: self.start_entrance_animation(), 0.08)
            return
        self._home_entrance_played = True
        self.animate_home()

    def stop_background_tasks(self) -> None:
        self._dashboard_load_seq += 1
        self.loading_skeleton_visible = False
        self.offline_banner_visible = False
        self._set_loading_guard(False)
        self._cancel_dashboard_timers()
        wallet_card = self._wallet_portfolio_card()
        if wallet_card is not None and hasattr(wallet_card, "stop_shimmer"):
            wallet_card.stop_shimmer()

    def _set_loading_guard(self, active: bool) -> None:
        self._loading = bool(active)
        self._is_loading = bool(active)
        try:
            self.home_controller.state.loading = bool(active)
        except Exception:
            pass

    def _bind_dashboard_events(self) -> None:
        if self._dashboard_events_bound:
            return
        app = MDApp.get_running_app()
        event_bus = getattr(app, "event_bus", None) if app else None
        subscribe = getattr(event_bus, "subscribe", None)
        if not callable(subscribe):
            return
        subscribe("WalletUpdated", self._on_wallet_updated)
        subscribe("TransactionCreated", self._on_transaction_created)
        subscribe("NotificationsUpdated", self._on_notifications_updated)
        self._dashboard_events_bound = True

    def _unbind_dashboard_events(self) -> None:
        if not self._dashboard_events_bound:
            return
        app = MDApp.get_running_app()
        event_bus = getattr(app, "event_bus", None) if app else None
        unsubscribe = getattr(event_bus, "unsubscribe", None)
        if callable(unsubscribe):
            unsubscribe("WalletUpdated", self._on_wallet_updated)
            unsubscribe("TransactionCreated", self._on_transaction_created)
            unsubscribe("NotificationsUpdated", self._on_notifications_updated)
        self._dashboard_events_bound = False

    def _on_wallet_updated(self, payload=None) -> None:
        self.refresh_dashboard()

    def _on_transaction_created(self, payload=None) -> None:
        try:
            snapshot = self.home_controller.merge_event_update("TransactionCreated", payload)
        except Exception:
            snapshot = {}
        transactions = list(snapshot.get("transactions") or [])
        if transactions:
            self._prepend_recent_transaction(transactions[0])
        self.refresh_dashboard()

    def _on_notifications_updated(self, payload=None) -> None:
        notification_count = 0
        if isinstance(payload, list):
            notification_count = len([item for item in payload if isinstance(item, dict)])
        elif isinstance(payload, dict):
            for key in ("notifications", "items", "results", "data"):
                rows = payload.get(key)
                if isinstance(rows, list):
                    notification_count = len([item for item in rows if isinstance(item, dict)])
                    break
        if notification_count <= 0:
            app = MDApp.get_running_app()
            app_state = getattr(app, "app_state", None) if app else None
            notifications = getattr(app_state, "notifications", []) if app_state is not None else []
            if isinstance(notifications, list):
                notification_count = len([item for item in notifications if isinstance(item, dict)])

        self.notification_badge_visible = notification_count > 0
        self.notification_count_text = str(min(9, notification_count)) if notification_count > 0 else "0"

    def _prepend_recent_transaction(self, transaction: dict) -> None:
        if not isinstance(transaction, dict):
            return
        container = self.ids.get("recent_container")
        if container is None:
            pending = list(self._recent_rows_pending or [])
            pending.insert(0, dict(transaction))
            self._recent_rows_pending = pending[:3]
            return
        widget = self._build_recent_item(transaction)
        widget.opacity = 0
        container.add_widget(widget)
        AnimationManager.fade_in(widget, duration=0.22)
        while len(container.children) > 3:
            container.remove_widget(container.children[-1])

    def _snapshot_has_content(self, snapshot: dict | None) -> bool:
        if not isinstance(snapshot, dict):
            return False
        return any(
            bool(snapshot.get(key))
            for key in ("profile", "user", "wallet", "transactions", "notifications", "recent_rows", "balance")
        )

    def _apply_dashboard_snapshot(self, snapshot: dict | None, *, load_seq: int | None = None, final: bool = True) -> None:
        if load_seq is not None and load_seq != self._dashboard_load_seq:
            return

        data = dict(snapshot or {})
        profile = data.get("profile") if isinstance(data.get("profile"), dict) else data.get("user")
        wallet = data.get("wallet") if isinstance(data.get("wallet"), dict) else {}
        transactions = list(data.get("transactions") or [])
        notifications = list(data.get("notifications") or [])
        greeting_name = str(data.get("greeting_name") or self._extract_first_name(profile or {}) or "").strip()

        balance_value = data.get("balance")
        if balance_value is None and isinstance(wallet, dict):
            balance_value = wallet.get("balance")

        notification_count = data.get("notification_count")
        if notification_count is None:
            notification_count = len(notifications)

        self._apply_home_data(
            greeting_name=greeting_name,
            balance=balance_value,
            recent_rows=transactions,
            error_text=str(data.get("error_text") or ""),
            is_agent_active=bool(data.get("is_agent_active", False)),
            reset_token=bool(data.get("reset_token", False)),
            is_verified=bool(data.get("is_verified", False)),
            is_admin=data.get("is_admin"),
            notification_count=notification_count,
            online=bool(data.get("online", True)),
            final=final,
        )

    @staticmethod
    def _resolve_avatar_source() -> str:
        return HomeScreen._resolve_asset_source(
            home_asset_path("02_header/profile_avatar.png"),
            "assets/avatar.png",
            "assets/profile.png",
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

    @staticmethod
    def _time_of_day_prefix() -> str:
        hour = datetime.now().hour
        if hour < 12:
            return "Good morning"
        if hour < 17:
            return "Good afternoon"
        return "Good evening"

    def _set_greeting(self, name: str = "") -> None:
        first_name = self._safe_first_name(name)
        self.time_of_day_text = self._time_of_day_prefix()
        self.greeting_text = f"Welcome back, {first_name}" if first_name else "Welcome back"

    def _update_balance_display(self) -> None:
        if self.balance_hidden:
            self.balance_display = "GH¢ ****.**"
            self.available_balance_display = "GH¢ ****.**"
            self.bonus_balance_display = "GH¢ ****.**"
        elif not self.wallet_balance_loaded:
            self.balance_display = self.balance_placeholder or "Syncing..."
            self.available_balance_display = self.balance_placeholder or "Syncing..."
            self.bonus_balance_display = "GH¢ 0.00"
        else:
            self.balance_display = f"GH¢ {float(self.wallet_balance_amount or 0.0):,.2f}"
            self.available_balance_display = self.balance_display
            self.bonus_balance_display = "GH¢ 0.00"

    def _set_agent_action_state(self, is_active: bool) -> None:
        self.is_agent_active = bool(is_active)
        if self.is_agent_active:
            self.agent_action_label = "Agent Dashboard"
            self.agent_action_hint = "Open Agent Dashboard"
        else:
            self.agent_action_label = "Become Agent"
            self.agent_action_hint = f"Pay GH¢ {AGENT_REGISTRATION_FEE_GHS:,.0f}"

    def _set_account_status(self, label: str, bg_color: list[float], text_color: list[float]) -> None:
        self.account_status_display = str(label or "").strip() or "SYNC"
        self.account_status_bg_color = list(bg_color or [0.12, 0.14, 0.18, 0.95])
        self.account_status_text_color = list(text_color or [0.86, 0.88, 0.90, 1])

    def toggle_balance(self) -> None:
        tap_feedback()
        self.balance_hidden = not self.balance_hidden
        self._update_balance_display()
        self._refresh_portfolio_values()
        hero_card = self.ids.get("hero_card") or (self._portfolio_cards.get("wallet") or {}).get("card")
        self._pulse_widget(hero_card)

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

    def _wallet_portfolio_card(self):
        return (self._portfolio_cards.get("wallet") or {}).get("card")

    def animate_home(self) -> None:
        """Run the dashboard entrance sequence from reusable animation helpers."""
        wallet_card = self.ids.get("wallet_hero_block")
        balance_panel = self.ids.get("portfolio_carousel")
        action_buttons = self.ids.get("quick_actions_block")
        promotions = self.ids.get("promotions_block")
        transactions = self.ids.get("transaction_list") or self.ids.get("transactions_block") or self.ids.get("recent_container")
        bottom_navigation = self.ids.get("bottom_navigation")

        DashboardAnimationSequence.play(
            wallet_card=wallet_card,
            balance_panel=balance_panel,
            action_buttons=action_buttons,
            promotions=promotions,
            transactions=transactions,
            bottom_navigation=bottom_navigation,
            shimmer_card=self._wallet_portfolio_card(),
        )

    def _ensure_dashboard_timers(self) -> None:
        if self._promo_scroll_event is None:
            self._promo_scroll_event = Clock.schedule_interval(lambda _dt: self._advance_promo_carousel(), 5)
        if self._market_refresh_event is None:
            self._market_refresh_event = Clock.schedule_interval(lambda _dt: self.refresh_market_data(silent=True), 60)

    def _cancel_dashboard_timers(self) -> None:
        for attr_name in ("_promo_scroll_event", "_market_refresh_event", "_dashboard_refresh_event"):
            event = getattr(self, attr_name, None)
            if event is not None:
                try:
                    event.cancel()
                except Exception:
                    pass
            setattr(self, attr_name, None)

    def _advance_promo_carousel(self, *_args) -> bool:
        carousel = self.ids.get("promo_carousel")
        slides = getattr(carousel, "slides", None)
        if carousel is None or not slides or len(slides) < 2:
            return True
        try:
            carousel.load_next(mode="next")
        except Exception:
            pass
        return True

    def refresh_market_data(self, silent: bool = False) -> None:
        if self._market_loading:
            return
        self._market_loading = True
        self._market_load_seq += 1
        seq = self._market_load_seq
        if not silent:
            self.market_status_text = "Refreshing..."
        threading.Thread(target=self._load_market_worker, args=(seq,), daemon=True).start()

    def refresh_dashboard(self) -> None:
        if self._loading:
            return
        self._loading = True
        self._is_loading = True
        self.balance_status = "Refreshing..."
        self._set_account_status("SYNC", [0.12, 0.14, 0.18, 0.95], [0.86, 0.88, 0.90, 1])
        self.load_dashboard(force=True)
        self.refresh_market_data(silent=False)

        if self._dashboard_refresh_event is not None:
            try:
                self._dashboard_refresh_event.cancel()
            except Exception:
                pass

        self._dashboard_refresh_event = Clock.schedule_once(self._finish_dashboard_refresh, 1.25)

    def _finish_dashboard_refresh(self, *_args) -> None:
        refresh_layout = self.ids.get("refresh_layout")
        if refresh_layout is not None:
            try:
                refresh_layout.refresh_done()
            except Exception:
                pass
        self._dashboard_refresh_event = None

    def _load_market_worker(self, seq: int) -> None:
        payload = self._fetch_market_snapshot()
        Clock.schedule_once(lambda _dt: self._apply_market_data(seq, payload), 0)

    def _fetch_market_snapshot(self) -> dict:
        return self.market_service.get_btc_snapshot()

    def _apply_market_data(self, seq: int, payload: dict) -> None:
        if seq != int(getattr(self, "_market_load_seq", 0)):
            return
        self._market_loading = False

        market_ok = isinstance(payload, dict) and not payload.get("error") and payload.get("last_price_usdt") is not None
        if market_ok:
            last_price = float(payload.get("last_price_usdt") or 0.0)
            change_percent = float(payload.get("price_change_percent_24h") or 0.0)
            usd_to_ghs_rate = float(payload.get("usd_to_ghs_rate") or 0.0)
            estimated_ghs_per_btc = float(payload.get("estimated_ghs_per_btc") or (last_price * usd_to_ghs_rate))
            updated_at = str(payload.get("updated_at") or "")

            self.market_btc_display = f"BTC ${last_price:,.0f}"
            self.market_fx_display = f"USD/GHS {usd_to_ghs_rate:,.2f}" if usd_to_ghs_rate else "USD/GHS 0.00"
            self.market_change_display = f"{change_percent:+.1f}% 24h"
            self.market_change_color = [0.54, 0.82, 0.67, 1] if change_percent >= 0 else [0.96, 0.47, 0.42, 1]
            self.market_change_icon = "trending-up" if change_percent >= 0 else "trending-down"
            self.market_status_text = "MARKET LIVE"
            self.market_status_color = [0.54, 0.82, 0.67, 1]
            self.market_updated_text = f"Updated {self._friendly_time(updated_at)}" if updated_at else "Updated recently"
            self.balance_status = self.balance_status or f"Estimated GHS {estimated_ghs_per_btc:,.2f}"
        else:
            self.market_btc_display = "BTC $0.00"
            self.market_fx_display = "USD/GHS 0.00"
            self.market_change_display = "+0.0% 24h"
            self.market_change_color = [0.74, 0.76, 0.80, 1]
            self.market_change_icon = "trending-up"
            self.market_status_text = "MARKET UNAVAILABLE"
            self.market_status_color = [0.94, 0.79, 0.46, 1]
            self.market_updated_text = "Price feed unavailable."

        self._market_snapshot = payload
        self._refresh_portfolio_values()

    def open_dashboard_help(self) -> None:
        show_message_dialog(
            self,
            title="Dashboard Tips",
            message=(
                "Tap the wallet balance to hide or show it, swipe the hero card for live wallet and market views, "
                "use the quick actions for your most common tasks, and open More for the full service list."
            ),
            close_label="Close",
        )

    def open_promo_cta(self, title: str, message: str) -> None:
        show_message_dialog(
            self,
            title=str(title or "Promotion").strip() or "Promotion",
            message=str(message or "Details will be available soon.").strip(),
            close_label="Close",
        )

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
        key_map = {0: "wallet", 1: "virtual_card", 2: "market"}
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
        return [
            {
                "key": "wallet",
                "title": "Wallet Balance",
                "value": self.balance_display,
                "subtitle": f"Available: {self.available_balance_display}",
                "caption": "Virtual Visa Card →",
                "icon": "wallet-outline",
                "accent": gold,
                "accent_bg": [gold[0], gold[1], gold[2], 0.20],
                "target": lambda: self.go_to("wallet"),
                "value_color": gold,
                "caption_color": text_secondary,
                "hint": f"Bonus: {self.bonus_balance_display}",
            },
            {
                "key": "virtual_card",
                "title": "Virtual Visa Card",
                "value": "Tap to spend",
                "subtitle": "Cards and controls.",
                "caption": "Open Cards →",
                "icon": "credit-card-outline",
                "accent": emerald,
                "accent_bg": [emerald[0], emerald[1], emerald[2], 0.18],
                "target": lambda: self.go_to("virtual_card"),
                "value_color": emerald,
                "caption_color": text_secondary,
                "hint": "Add money or withdraw",
            },
            {
                "key": "market",
                "title": "Market Pulse",
                "value": self.market_btc_display,
                "subtitle": "Live BTC + FX",
                "caption": self.market_change_display,
                "icon": "chart-line",
                "accent": btc,
                "accent_bg": [btc[0], btc[1], btc[2], 0.18],
                "target": lambda: self.go_to("btc"),
                "value_color": btc,
                "caption_color": self.market_change_color,
                "hint": self.market_fx_display,
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

        is_wallet_card = str(spec.get("key", "")) == "wallet"
        card_cls = WalletCard if is_wallet_card else MDCard
        card = card_cls(
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

        title_stack = MDBoxLayout(
            orientation="vertical", 
            spacing=dp(2 * layout_scale),
            adaptive_height=True,
            pos_hint={"center_y": 0.5}
        )
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

        value_label_class = BalanceLabel if is_wallet_card else MDLabel
        value_label = value_label_class(
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
        if is_wallet_card and isinstance(value_label, BalanceCounter):
            value_label.currency_symbol = "GH₵"
            value_label.highlight_color = list(spec["value_color"])
            value_label.normal_color = list(spec["value_color"])
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
                if (
                    isinstance(wallet_label, BalanceCounter)
                    and self.wallet_balance_loaded
                    and not self.balance_hidden
                ):
                    wallet_label.animate_balance(float(self.wallet_balance_amount or 0.0))
                elif isinstance(wallet_label, BalanceCounter):
                    wallet_label.set_static_text(self.balance_display)
                else:
                    wallet_label.text = self.balance_display
            hint_label = wallet.get("hint_label")
            if hint_label is not None:
                hint_label.text = f"Bonus: {self.bonus_balance_display}"

        market = self._portfolio_cards.get("market")
        if market:
            market_label = market.get("value_label")
            if market_label is not None:
                market_label.text = self.market_btc_display
            market_hint = market.get("hint_label")
            if market_hint is not None:
                market_hint.text = self.market_fx_display
            market_caption = market.get("caption_label")
            if market_caption is not None:
                market_caption.text = self.market_change_display
                market_caption.text_color = self.market_change_color

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
            if direction == "receive" or amount >= 0:
                return "Money Received"
            recipient_name = str(
                metadata.get("recipient_name")
                or metadata.get("beneficiary_name")
                or metadata.get("counterparty_name")
                or metadata.get("name")
                or ""
            ).strip()
            if recipient_name:
                return f"Transfer to {self._safe_first_name(recipient_name) or recipient_name}"
            return "Money Sent"

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

    def _build_empty_recent_item(self) -> MDCard:
        layout_scale = float(self.layout_scale or 1.0)
        text_scale = float(self.text_scale or 1.0)

        card = MDCard(
            size_hint_y=None,
            height=dp(72 * layout_scale),
            radius=[dp(16 * layout_scale)],
            md_bg_color=TX_CARD_BG,
            padding=[dp(12 * layout_scale), dp(10 * layout_scale), dp(12 * layout_scale), dp(10 * layout_scale)],
            line_color=[0.22, 0.24, 0.28, 0.60],
            elevation=0,
        )
        card.add_widget(
            MDLabel(
                text="No recent activity",
                font_name=FONT_SEMIBOLD,
                font_size=sp(14 * text_scale),
                theme_text_color="Custom",
                text_color=[0.72, 0.72, 0.74, 1],
                halign="center",
                valign="center",
            )
        )
        return card

    def _set_balance_unavailable(self, placeholder: str, status_text: str) -> None:
        self.wallet_balance_loaded = False
        self.balance_placeholder = str(placeholder or "Sync unavailable").strip()
        self.balance_status = str(status_text or "Balance sync unavailable").strip()
        self._update_balance_display()

    def _build_recent_item(self, tx: dict) -> MDCard:
        amount = float(tx.get("amount", 0.0) or 0.0)
        metadata = self._parse_metadata(tx)
        tx_type = str(tx.get("type", "") or "").strip().lower()
        direction = str(metadata.get("direction", "") or "").strip().lower()
        positive = amount >= 0 or direction == "receive"
        sign = "+" if positive else "-"
        layout_scale = float(self.layout_scale or 1.0)
        text_scale = float(self.text_scale or 1.0)
        icon_scale = float(self.icon_scale or 1.0)
        if tx_type == "transfer":
            if positive:
                icon_name = "arrow-down"
                icon_color = [0.45, 0.89, 0.58, 1]
                icon_bg = [0.12, 0.33, 0.19, 0.96]
                icon_line = [0.36, 0.69, 0.45, 0.34]
            else:
                icon_name = "wallet-outline"
                icon_color = [0.36, 0.56, 1.0, 1]
                icon_bg = [0.10, 0.21, 0.42, 0.96]
                icon_line = [0.28, 0.48, 0.88, 0.30]
        elif tx_type in {"airtime", "data", "pay_bill", "bill", "bills", "utility"}:
            icon_name = "arrow-top-right"
            icon_color = [0.98, 0.74, 0.15, 1]
            icon_bg = [0.30, 0.20, 0.08, 0.96]
            icon_line = [0.86, 0.65, 0.18, 0.30]
        else:
            icon_name = "arrow-down"
            icon_color = POSITIVE_COLOR if positive else NEGATIVE_COLOR
            icon_bg = [0.22, 0.34, 0.24, 0.96] if positive else [0.33, 0.18, 0.15, 0.96]
            icon_line = [0.50, 0.74, 0.57, 0.34] if positive else [0.86, 0.47, 0.39, 0.28]
        raw_subtitle = str(
            tx.get("subtitle")
            or metadata.get("subtitle")
            or metadata.get("description")
            or metadata.get("counterparty_name")
            or metadata.get("beneficiary_name")
            or metadata.get("recipient_name")
            or metadata.get("network")
            or ""
        ).strip()
        if tx_type == "transfer" and positive and raw_subtitle and not raw_subtitle.lower().startswith("from"):
            subtitle_text = f"From: {raw_subtitle}"
        elif tx_type == "transfer" and not positive and raw_subtitle and not raw_subtitle.lower().startswith("to"):
            subtitle_text = f"To: {raw_subtitle}"
        elif tx_type == "transfer" and not raw_subtitle:
            subtitle_text = "Mobile Money"
        else:
            subtitle_text = raw_subtitle or ("Mobile Money" if tx_type == "transfer" else "Recent activity")

        card = MDCard(
            size_hint_y=None,
            height=dp(88 * layout_scale),
            radius=[dp(18 * layout_scale)],
            md_bg_color=[0.08, 0.08, 0.09, 0.94],
            padding=[dp(12 * layout_scale), dp(10 * layout_scale), dp(12 * layout_scale), dp(10 * layout_scale)],
            line_color=[0.32, 0.32, 0.36, 0.70],
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
        icon_anchor = AnchorLayout(anchor_x="center", anchor_y="center")
        icon_anchor.add_widget(
            MDIconButton(
                icon=icon_name,
                size_hint=(None, None),
                size=(dp(22 * layout_scale), dp(22 * layout_scale)),
                theme_text_color="Custom",
                text_color=icon_color,
                user_font_size=f"{20 * icon_scale:.1f}sp",
                disabled=True,
            )
        )
        icon_wrap.add_widget(icon_anchor)

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
                text=subtitle_text,
                font_name=FONT_REGULAR,
                font_size=sp(11 * text_scale),
                theme_text_color="Custom",
                text_color=[0.72, 0.72, 0.74, 1],
                shorten=True,
                shorten_from="right",
            )
        )

        amount_stack = MDBoxLayout(orientation="vertical", spacing=dp(1 * layout_scale), size_hint_x=None, width=dp(132 * layout_scale))
        amount_stack.add_widget(
            MDLabel(
                text=f"{sign} GH¢ {self._format_amount(abs(amount))}",
                halign="right",
                valign="center",
                font_name=FONT_SEMIBOLD,
                font_size=sp(15 * text_scale),
                bold=True,
                theme_text_color="Custom",
                text_color=icon_color,
            )
        )
        amount_stack.add_widget(
            MDLabel(
                text=self._friendly_time(str(tx.get("timestamp", "") or "")),
                halign="right",
                valign="center",
                font_name=FONT_REGULAR,
                font_size=sp(11 * text_scale),
                theme_text_color="Custom",
                text_color=[0.72, 0.72, 0.74, 1],
            )
        )

        menu_button = MDIconButton(
            icon="dots-vertical",
            size_hint=(None, None),
            size=(dp(28 * layout_scale), dp(28 * layout_scale)),
            theme_text_color="Custom",
            text_color=[0.74, 0.74, 0.78, 1],
            user_font_size=f"{18 * icon_scale:.1f}sp",
        )

        row.add_widget(icon_wrap)
        row.add_widget(text_col)
        row.add_widget(amount_stack)
        row.add_widget(menu_button)
        card.add_widget(row)
        return card

    def _render_recent_activity(self, rows: list[dict]) -> None:
        container = self.ids.get("recent_container")
        if container is None:
            if not getattr(self, "_recent_activity_retry_scheduled", False):
                self._recent_activity_retry_scheduled = True
                Logger.warning("CyberCashHome: recent_container is not ready; retrying recent activity render")
                Clock.schedule_once(lambda _dt: self._render_recent_activity(rows), 0)
            return
        self._recent_activity_retry_scheduled = False
        container.clear_widgets()
        self._recent_render_sequence += 1
        render_sequence = self._recent_render_sequence

        def _queue_widget(widget, delay: float) -> None:
            def _start(_dt):
                if render_sequence != self._recent_render_sequence:
                    return
                widget.opacity = 0
                container.add_widget(widget)
                AnimationManager.fade_in(widget, duration=0.28)

            Clock.schedule_once(_start, delay)

        if not rows:
            _queue_widget(self._build_empty_recent_item(), 0)
            return

        for index, tx in enumerate(rows[:3]):
            _queue_widget(self._build_recent_item(tx), index * 0.08)

    def _apply_signed_out_state(self, greeting_name: str = "") -> None:
        self._set_greeting(greeting_name)
        self._set_balance_unavailable("Sign in", "Sign in to view live wallet")
        self._set_agent_action_state(False)
        self._set_account_status("SIGN IN", [0.12, 0.14, 0.18, 0.95], [0.86, 0.88, 0.90, 1])
        self.dashboard_ready = False
        self.loading_skeleton_visible = False
        self.offline_banner_visible = False
        self.notification_count_text = "0"
        self.notification_badge_visible = False
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

    @staticmethod
    def _should_clear_session(status_code: int, payload: object, *, auth_gate: bool = False) -> bool:
        """Clear saved login only when the backend says the session itself is invalid."""
        try:
            code = int(status_code or 0)
        except Exception:
            code = 0
        detail = extract_backend_message(payload).lower()
        invalid_markers = (
            "could not validate credentials",
            "invalid token",
            "not authenticated",
            "token expired",
            "session expired",
            "inactive",
            "revoked",
            "expired",
        )
        if code == 401:
            return bool(auth_gate) or any(marker in detail for marker in invalid_markers)
        if code != 403 or not auth_gate:
            return False
        return any(marker in detail for marker in invalid_markers)

    @staticmethod
    def _api_get(path: str, headers: dict, params: dict | None = None) -> tuple[int, object]:
        response = api.get(path, params=params, headers=headers, timeout=FAST_TIMEOUT)
        return int(getattr(response, "status_code", 0) or 0), response.json()

    def _load_home_worker(self, token: str, load_seq: int) -> None:
        headers = {"Authorization": f"Bearer {token}"}
        app = MDApp.get_running_app()
        greeting_name = str(getattr(app, "user_name", "") or "").strip()
        if greeting_name == "Cyber Cash User":
            greeting_name = ""
        is_admin = bool(getattr(app, "is_admin", False)) if app else False
        is_verified = False
        is_agent_active = False
        reset_token = False
        error_text = ""
        balance = None
        recent_rows: list[dict] = []
        notification_count = 0
        dashboard_snapshot: dict = {}

        try:
            me_status, me_payload = self._api_get("/auth/me", headers=headers)
            if self._should_clear_session(me_status, me_payload, auth_gate=True):
                Logger.info("CyberCashAuth: auth gate rejected saved session; returning to login")
                reset_token = True
            if me_status < 400 and isinstance(me_payload, dict):
                greeting_name = self._extract_first_name(me_payload) or greeting_name
                is_admin = bool(
                    me_payload.get("is_admin")
                    or str(me_payload.get("role", "") or "").strip().lower() in {"admin", "super_admin"}
                )
        except Exception:
            pass

        if not reset_token:
            try:
                dashboard_snapshot = self.home_controller.load_dashboard_state()
            except Exception as exc:
                error_text = str(exc or "").strip() or "Check connection and try again."
                dashboard_snapshot = {}

            if not isinstance(dashboard_snapshot, dict):
                dashboard_snapshot = {}

            profile = dashboard_snapshot.get("profile") if isinstance(dashboard_snapshot.get("profile"), dict) else {}
            wallet = dashboard_snapshot.get("wallet") if isinstance(dashboard_snapshot.get("wallet"), dict) else {}
            recent_rows = list(dashboard_snapshot.get("transactions") or [])
            notification_count = int(dashboard_snapshot.get("notification_count") or len(dashboard_snapshot.get("notifications") or []))

            if profile:
                greeting_name = self._extract_first_name(profile) or greeting_name
                is_admin = bool(
                    profile.get("is_admin")
                    or str(profile.get("role", "") or "").strip().lower() in {"admin", "super_admin"}
                    or is_admin
                )
                is_verified = bool(
                    profile.get("is_verified")
                    or profile.get("verified")
                    or wallet.get("verified")
                    or wallet.get("status") == "verified"
                    or dashboard_snapshot.get("is_verified")
                )
                is_agent_active = bool(
                    profile.get("is_agent")
                    or profile.get("agent_active")
                    or dashboard_snapshot.get("is_agent_active")
                )

            if dashboard_snapshot.get("balance") is not None:
                try:
                    balance = float(dashboard_snapshot.get("balance") or 0.0)
                except Exception:
                    balance = None
            elif wallet:
                try:
                    balance = float(wallet.get("balance", 0.0) or 0.0)
                except Exception:
                    balance = None

            if not error_text:
                error_text = str(dashboard_snapshot.get("error_text") or "")
            if not error_text and str(dashboard_snapshot.get("source") or "") != "live":
                error_text = "Check connection and try again."

            try:
                v_status, v_payload = self._api_get("/wallet/verify", headers=headers)
                if v_status < 400 and isinstance(v_payload, dict):
                    is_verified = bool(v_payload.get("status") == "verified" or is_verified)
                    if not is_verified and v_payload.get("difference", 0) != 0:
                        Logger.warning("CyberCashLedger: Balance mismatch detected: %s", v_payload.get("difference"))
            except Exception:
                pass

            try:
                agent_status_code, agent_payload = self._api_get("/agents/me", headers=headers)
                if self._should_clear_session(agent_status_code, agent_payload):
                    reset_token = True
                elif agent_status_code < 400 and isinstance(agent_payload, dict):
                    status_value = str(agent_payload.get("status", "") or "").strip().lower()
                    is_agent_active = status_value == "active"
                else:
                    Logger.info("CyberCashAuth: agent refresh unavailable with HTTP %s; keeping session", agent_status_code)
            except Exception:
                is_agent_active = False

        dashboard_snapshot.update(
            {
                "greeting_name": greeting_name,
                "balance": balance,
                "transactions": recent_rows,
                "error_text": error_text,
                "is_agent_active": is_agent_active,
                "reset_token": reset_token,
                "is_verified": is_verified,
                "is_admin": is_admin,
                "notification_count": notification_count,
                "online": bool(dashboard_snapshot.get("online", True)) and not reset_token,
            }
        )
        Clock.schedule_once(
            lambda _dt, snap=dashboard_snapshot, seq=load_seq: self._apply_dashboard_snapshot(snap, load_seq=seq)
        )

    def _apply_home_data(
        self,
        greeting_name: str = "",
        balance: float | None = None,
        recent_rows: list[dict] | None = None,
        error_text: str = "",
        is_agent_active: bool = False,
        reset_token: bool = False,
        is_verified: bool = False,
        is_admin: bool | None = None,
        notification_count: int | None = None,
        online: bool = True,
        final: bool = True,
    ) -> None:
        if final:
            self._set_loading_guard(False)
        previous_balance = float(self.wallet_balance_amount or 0.0)
        had_loaded_balance = bool(self.wallet_balance_loaded)
        if reset_token:
            app = MDApp.get_running_app()
            app.access_token = ""
            app.pending_momo = ""
            app.user_name = "Cyber Cash User"
            app.is_admin = False
            save_token("")
            self._apply_signed_out_state()
            self._set_loading_guard(False)
            app = MDApp.get_running_app()
            if app is not None and hasattr(app, "go_to_screen"):
                app.go_to_screen("login", fallback="", transition_style="fade")
            elif self.manager:
                navigate(self.manager, "login", fallback="", transition_style="fade")
            return
        if greeting_name:
            self._set_greeting(greeting_name)
            app = MDApp.get_running_app()
            if app:
                app.user_name = greeting_name

        if is_admin is not None:
            app = MDApp.get_running_app()
            if app:
                app.is_admin = bool(is_admin)

        if balance is None:
            if self.wallet_balance_loaded:
                self.balance_status = error_text or "Live balance shown; sync pending"
            else:
                self._set_balance_unavailable("Sync unavailable", error_text or "Balance sync unavailable")
                self._set_account_status(
                    "OFFLINE" if (error_text or not online) else "SYNC",
                    [0.22, 0.16, 0.11, 0.95] if (error_text or not online) else [0.12, 0.14, 0.18, 0.95],
                    [0.98, 0.88, 0.68, 1] if (error_text or not online) else [0.86, 0.88, 0.90, 1],
                )
        else:
            self.wallet_balance_loaded = True
            self.balance_placeholder = ""
            self.wallet_balance_amount = float(balance)
            self._update_balance_display()
            self.balance_status = ("Verified balance ✓" if is_verified else "Live balance") if not error_text else error_text
            self._set_account_status(
                "VERIFIED" if is_verified else ("OFFLINE" if not online else "LIVE"),
                [0.18, 0.31, 0.22, 0.95] if is_verified else ([0.22, 0.16, 0.11, 0.95] if not online else [0.14, 0.22, 0.17, 0.95]),
                [0.70, 0.92, 0.78, 1] if is_verified else ([0.98, 0.88, 0.68, 1] if not online else [0.86, 0.90, 0.88, 1]),
            )

        self._set_agent_action_state(is_agent_active)
        self._render_recent_activity(recent_rows or [])
        try:
            recent_count = int(notification_count if notification_count is not None else len(recent_rows or []) or 0)
        except Exception:
            recent_count = len(recent_rows or [])
        self.notification_badge_visible = recent_count > 0
        self.notification_count_text = str(min(9, recent_count)) if recent_count > 0 else "0"
        if not online or error_text:
            self.offline_banner_visible = True
            self.offline_banner_text = str(error_text or "Offline mode").strip() or "Offline mode"
        else:
            self.offline_banner_visible = False
            self.offline_banner_text = "Offline mode"
        self._refresh_portfolio_values()
        if balance is not None:
            new_balance = float(balance or 0.0)
            balance_changed = abs(previous_balance - new_balance) > 0.005 or not had_loaded_balance
            if balance_changed:
                wallet_card = self._wallet_portfolio_card()
                if wallet_card is not None and hasattr(wallet_card, "pulse"):
                    wallet_card.pulse()
        self.dashboard_ready = True
        self.loading_skeleton_visible = False

    def load_home_data(self, force: bool = False) -> None:
        if self._loading and not force:
            return

        app = MDApp.get_running_app()
        token = str(getattr(app, "access_token", "") or "").strip()
        cached_name = str(getattr(app, "user_name", "") or "").strip()
        pending_name = str(getattr(app, "pending_momo", "") or "").strip()
        display_name = cached_name if cached_name and cached_name != "Cyber Cash User" else pending_name

        if display_name and not display_name.isdigit():
            self._set_greeting(display_name)

        if not token:
            self._set_loading_guard(False)
            self._apply_signed_out_state(pending_name if not pending_name.isdigit() else "")
            return

        self._dashboard_load_seq += 1
        load_seq = self._dashboard_load_seq
        previous_ready = bool(self.dashboard_ready)
        self._set_loading_guard(True)
        self.dashboard_ready = previous_ready if force else False
        self.loading_skeleton_visible = not force
        self.offline_banner_visible = False
        self._set_account_status("SYNC", [0.12, 0.14, 0.18, 0.95], [0.86, 0.88, 0.90, 1])
        if not self.wallet_balance_loaded:
            self.balance_placeholder = "Syncing..."
            self._update_balance_display()
        self.balance_status = "Refreshing..."
        self._refresh_portfolio_values()
        if not force:
            try:
                cached_snapshot = self.home_controller.load_cached_dashboard_state()
            except Exception as exc:
                Logger.warning("CyberCashHome: failed to load cached dashboard: %s", exc)
                cached_snapshot = {}
            if self._snapshot_has_content(cached_snapshot):
                self._apply_dashboard_snapshot(cached_snapshot, load_seq=load_seq, final=False)
        threading.Thread(target=self._load_home_worker, args=(token, load_seq), daemon=True).start()

    def load_dashboard(self, force: bool = False) -> None:
        self.load_home_data(force=force)

    def populate_dashboard(self, wallet: dict | None, transactions: list[dict] | None) -> None:
        balance = None
        if isinstance(wallet, dict):
            try:
                balance = float(wallet.get("balance", 0.0) or 0.0)
            except Exception:
                balance = None
        self._apply_home_data(
            balance=balance,
            recent_rows=list(transactions or []),
            error_text="",
            online=True,
            final=True,
        )

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
                f"Pay GH¢ {AGENT_REGISTRATION_FEE_GHS:,.2f} to become an agent. "
                f"After payment, we activate your Agent Dashboard and add GH¢ {AGENT_STARTUP_LOAN_GHS:,.2f} startup float."
            ),
            on_confirm=self._initiate_agent_registration,
            confirm_label=f"Pay GH¢ {AGENT_REGISTRATION_FEE_GHS:,.0f}",
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
            response = api.request(
                "POST",
                "/agents/register",
                headers=headers,
                timeout=(4, 15),
            )
            payload = response.json()
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
                f"Pay GH¢ {AGENT_REGISTRATION_FEE_GHS:,.2f} with Paystack. "
                f"We'll activate your Agent Dashboard and add GH¢ {AGENT_STARTUP_LOAN_GHS:,.2f} startup float after payment."
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
            opened_in_browser = False
            if not opened_in_app:
                try:
                    opened_in_browser = bool(webbrowser.open(authorization_url, new=2))
                except Exception:
                    opened_in_browser = False
            if not opened_in_app and not opened_in_browser:
                show_message_dialog(
                    self,
                    title="Paystack",
                    message=(
                        "Checkout could not open automatically. "
                        f"Keep this reference and try again: {reference or 'pending'}"
                    ),
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
                response = api.request(
                    "GET",
                    f"/agents/register/verify/{reference}",
                    headers=headers,
                    timeout=(4, 12),
                )
                payload = response.json()

                if response.status_code < 400 and isinstance(payload, dict):
                    status_value = str(payload.get("status", "") or "").strip().lower()
                    if status_value == "active":
                        Clock.schedule_once(lambda _dt, p=payload: self._on_agent_registration_success(p))
                        return
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
                f"Payment confirmed.\nGH¢ {AGENT_STARTUP_LOAN_GHS:,.2f} startup float credited."
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
            response = api.get("/agents/me", headers=headers, timeout=(4, 12))
            payload = response.json()
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
        tap_feedback()
        app = MDApp.get_running_app()
        if app is not None and hasattr(app, "go_to_screen"):
            app.go_to_screen(screen_name)
            return
        if self.manager:
            navigate(
                self.manager,
                screen_name,
                fallback=str(getattr(self.manager, "current", "home") or "home"),
                transition_style="fade",
            )


class MoreActionsContent(MDBoxLayout):
    controller = ObjectProperty()
    layout_scale = NumericProperty(1.0)
    text_scale = NumericProperty(1.0)
    icon_scale = NumericProperty(1.0)
    compact_mode = BooleanProperty(False)
    agent_action_label = StringProperty("Become Agent")
    agent_fee_hint = StringProperty(f"Pay GH¢ {AGENT_REGISTRATION_FEE_GHS:,.0f}")

    def trigger_action(self, screen_name: str) -> None:
        if self.controller:
            self.controller.handle_more_action(str(screen_name or ""))
kv_path = os.path.join(os.path.dirname(__file__), "home_dashboard.kv")
with open(kv_path, "r", encoding="utf-8-sig") as kv_file:
    Builder.load_string(kv_file.read(), filename=kv_path)
