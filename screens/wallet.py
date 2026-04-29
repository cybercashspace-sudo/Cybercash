from datetime import datetime
import threading
import time
import webbrowser

from kivy.clock import Clock
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import BooleanProperty, ColorProperty, StringProperty
from kivymd.app import MDApp

from api.client import api_client
from core.screen_actions import ActionScreen
from core.paystack_checkout import open_paystack_checkout, warmup_paystack_checkout
from utils.network import normalize_ghana_number

MIN_PAYSTACK_DEPOSIT_GHS = 1.0
MIN_WITHDRAW_TO_AGENT_GHS = 1.0
PAYSTACK_VERIFY_POLL_INTERVAL_SECONDS = 3
PAYSTACK_VERIFY_MAX_POLLS = 40

KV = """
#:import dp kivy.metrics.dp
#:import sp kivy.metrics.sp
#:set BG (0.03, 0.04, 0.06, 1)
#:set SURFACE (0.08, 0.10, 0.14, 0.95)
#:set SURFACE_SOFT (0.12, 0.14, 0.18, 0.95)
#:set GOLD (0.94, 0.79, 0.46, 1)
#:set GOLD_SOFT (0.93, 0.77, 0.39, 1)
#:set GREEN_CARD (0.24, 0.43, 0.34, 0.96)
#:set TEXT_MAIN (0.95, 0.95, 0.95, 1)
#:set TEXT_SUB (0.74, 0.76, 0.80, 1)
<WalletScreen>:
    MDBoxLayout:
        orientation: "vertical"

        canvas.before:
            Color:
                rgba: BG
            Rectangle:
                pos: self.pos
                size: self.size

        MDBoxLayout:
            orientation: "vertical"
            size_hint_y: None
            height: 0
            opacity: 0
            disabled: True
            padding: [dp(16 * root.layout_scale), dp(16 * root.layout_scale), dp(16 * root.layout_scale), dp(10 * root.layout_scale)]
            spacing: dp(10 * root.layout_scale)

            MDBoxLayout:
                size_hint_y: None
                height: dp(52 * root.layout_scale)

                MDLabel:
                    text: root.page_title
                    font_style: "Title"
                    font_size: sp(22 * root.text_scale)
                    bold: True
                    theme_text_color: "Custom"
                    text_color: GOLD

                MDTextButton:
                    text: "Back"
                    theme_text_color: "Custom"
                    text_color: GOLD
                    on_release: root.go_back()

            MDLabel:
                text: root.greeting_text
                theme_text_color: "Custom"
                text_color: TEXT_MAIN
                font_size: sp(14 * root.text_scale)
                size_hint_y: None
                height: self.texture_size[1] if self.text else 0
                shorten: True
                shorten_from: "right"

            MDCard:
                radius: [dp(22 * root.layout_scale)]
                md_bg_color: GREEN_CARD
                elevation: 0
                size_hint_y: None
                height: dp(140 * root.layout_scale)
                padding: [dp(14 * root.layout_scale)] * 4
                MDBoxLayout:
                    orientation: "vertical"
                    spacing: dp(4 * root.layout_scale)
                    adaptive_height: True

                    MDLabel:
                        text: "Wallet Balance"
                        theme_text_color: "Custom"
                        text_color: TEXT_MAIN

                    MDLabel:
                        text: root.balance_display
                        font_style: "Headline"
                        bold: True
                        theme_text_color: "Custom"
                        text_color: GOLD
                        font_size: sp(28 * root.text_scale)

                    MDLabel:
                        text: root.wallet_status if root.wallet_status and root.wallet_status != "Live wallet balance" else "Credits after Paystack confirms."
                        theme_text_color: "Custom"
                        text_color: 0.80, 0.92, 0.80, 1
                        font_size: sp(12 * root.text_scale)
                        size_hint_y: None
                        height: self.texture_size[1] if self.text else 0
                        shorten: True
                        shorten_from: "right"

        ScrollView:
            id: content_scroll
            do_scroll_x: False
            bar_width: 0

            MDBoxLayout:
                orientation: "vertical"
                size_hint_y: None
                height: self.minimum_height
                padding: [dp(16 * root.layout_scale), dp(16 * root.layout_scale), dp(16 * root.layout_scale), dp(18 * root.layout_scale)]
                spacing: dp((10 if root.screen_mode == "all" else 8) * root.layout_scale)

                MDBoxLayout:
                    orientation: "vertical"
                    size_hint_y: None
                    height: self.minimum_height
                    opacity: 1
                    spacing: dp(10 * root.layout_scale)

                    MDBoxLayout:
                        size_hint_y: None
                        height: dp(52 * root.layout_scale)

                        MDLabel:
                            text: root.page_title
                            font_style: "Title"
                            font_size: sp(22 * root.text_scale)
                            bold: True
                            theme_text_color: "Custom"
                            text_color: GOLD

                        MDTextButton:
                            text: "Back"
                            theme_text_color: "Custom"
                            text_color: GOLD
                            on_release: root.go_back()

                    MDLabel:
                        text: root.page_subtitle
                        theme_text_color: "Custom"
                        text_color: TEXT_SUB
                        font_size: sp(12.5 * root.text_scale)
                        adaptive_height: True

                    MDCard:
                        radius: [dp(22 * root.layout_scale)]
                        md_bg_color: GREEN_CARD
                        elevation: 0
                        size_hint_y: None
                        height: dp(134 * root.layout_scale) if root.screen_mode == "withdraw" else 0
                        opacity: 1 if root.screen_mode == "withdraw" else 0
                        disabled: True if root.screen_mode != "withdraw" else False
                        padding: [dp(14 * root.layout_scale)] * 4

                        MDBoxLayout:
                            orientation: "vertical"
                            spacing: dp(4 * root.layout_scale)

                            MDLabel:
                                text: "Available Balance"
                                theme_text_color: "Custom"
                                text_color: TEXT_MAIN

                            MDLabel:
                                text: root.balance_display
                                font_style: "Headline"
                                bold: True
                                theme_text_color: "Custom"
                                text_color: GOLD
                                font_size: sp(28 * root.text_scale)

                            MDLabel:
                                text: root.wallet_status
                                theme_text_color: "Custom"
                                text_color: 0.80, 0.92, 0.80, 1
                                font_size: sp(12 * root.text_scale)

                    MDCard:
                        radius: [dp(22 * root.layout_scale)]
                        md_bg_color: GREEN_CARD
                        elevation: 0
                        size_hint_y: None
                        height: dp((124 if not root.wallet_status or root.wallet_status == "Live wallet balance" else 140) * root.layout_scale) if root.screen_mode == "all" else 0
                        opacity: 1 if root.screen_mode == "all" else 0
                        disabled: True if root.screen_mode != "all" else False
                        padding: [dp(14 * root.layout_scale)] * 4
                        MDBoxLayout:
                            orientation: "vertical"
                            spacing: dp(4 * root.layout_scale)
                            adaptive_height: True

                            MDLabel:
                                text: "Wallet Balance"
                                theme_text_color: "Custom"
                                text_color: TEXT_MAIN

                            MDLabel:
                                text: root.balance_display
                                font_style: "Headline"
                                bold: True
                                theme_text_color: "Custom"
                                text_color: GOLD
                                font_size: sp(28 * root.text_scale)

                            MDLabel:
                                text: root.wallet_status if root.wallet_status and root.wallet_status != "Live wallet balance" else ""
                                theme_text_color: "Custom"
                                text_color: 0.80, 0.92, 0.80, 1
                                font_size: sp(12 * root.text_scale)
                                size_hint_y: None
                                height: self.texture_size[1] if self.text else 0
                                shorten: True
                                shorten_from: "right"

                    MDBoxLayout:
                        orientation: "vertical"
                        adaptive_height: True
                        spacing: dp((10 if root.screen_mode == "all" else 0) * root.layout_scale)

                        MDCard:
                            id: deposit_section
                            size_hint_y: None
                            height: deposit_section_content.height + dp(28 * root.layout_scale) if root.screen_mode != "withdraw" else 0
                            opacity: 1 if root.screen_mode != "withdraw" else 0
                            radius: [dp(20 * root.layout_scale)]
                            md_bg_color: SURFACE
                            elevation: 0
                            padding: [dp(14 * root.layout_scale)] * 4

                            MDBoxLayout:
                                id: deposit_section_content
                                orientation: "vertical"
                                adaptive_height: True
                                spacing: dp(10 * root.layout_scale)

                                MDBoxLayout:
                                    size_hint_y: None
                                    height: dp(40 * root.layout_scale)
                                    spacing: dp(10 * root.layout_scale)

                                    MDCard:
                                        size_hint: None, None
                                        size: dp(34 * root.layout_scale), dp(34 * root.layout_scale)
                                        radius: [dp(11 * root.layout_scale)]
                                        md_bg_color: GOLD_SOFT
                                        elevation: 0

                                        MDIconButton:
                                            icon: "credit-card-check-outline"
                                            user_font_size: str(18 * root.icon_scale) + "sp"
                                            size_hint: None, None
                                            size: dp(22 * root.layout_scale), dp(22 * root.layout_scale)
                                            pos_hint: {"center_x": 0.5, "center_y": 0.5}
                                            theme_text_color: "Custom"
                                            text_color: BG
                                            disabled: True

                                    MDLabel:
                                        text: "Paystack Deposit"
                                        theme_text_color: "Custom"
                                        text_color: GOLD
                                        bold: True
                                        valign: "middle"
                                        shorten: True
                                        shorten_from: "right"

                                    Widget:

                                    MDLabel:
                                        text: "Min GHS 1.00"
                                        theme_text_color: "Custom"
                                        text_color: TEXT_SUB
                                        font_size: sp(11.5 * root.text_scale)
                                        valign: "middle"
                                        halign: "right"

                                MDLabel:
                                    text: "Amount (GHS)"
                                    theme_text_color: "Custom"
                                    text_color: TEXT_MAIN
                                    bold: True
                                    adaptive_height: True

                                MDTextField:
                                    id: deposit_amount
                                    hint_text: "Amount in GHS (e.g. 15.50)"
                                    mode: "outlined"
                                    input_filter: "float"
                                    on_text: root.update_deposit_preview(self.text)

                                MDLabel:
                                    text: root.deposit_preview
                                    theme_text_color: "Custom"
                                    text_color: TEXT_SUB
                                    font_size: sp(11.5 * root.text_scale)
                                    adaptive_height: True

                                MDLabel:
                                    text: "Wallet credits after Paystack confirms."
                                    theme_text_color: "Custom"
                                    text_color: TEXT_SUB
                                    font_size: sp(11.25 * root.text_scale)
                                    size_hint_y: None
                                    height: self.texture_size[1] if root.screen_mode != "all" else 0
                                    opacity: 1 if root.screen_mode != "all" else 0

                                MDLabel:
                                    text: "Quick Amounts"
                                    theme_text_color: "Custom"
                                    text_color: TEXT_MAIN
                                    bold: True
                                    adaptive_height: True

                                MDGridLayout:
                                    cols: 2 if root.compact_mode else 4
                                    spacing: dp(6 * root.layout_scale)
                                    size_hint_y: None
                                    height: self.minimum_height

                                    MDRaisedButton:
                                        text: "1"
                                        md_bg_color: SURFACE_SOFT
                                        text_color: TEXT_MAIN
                                        size_hint_y: None
                                        height: dp(42 * root.layout_scale)
                                        on_release: root.set_deposit_amount(1)
                                    MDRaisedButton:
                                        text: "5"
                                        md_bg_color: SURFACE_SOFT
                                        text_color: TEXT_MAIN
                                        size_hint_y: None
                                        height: dp(42 * root.layout_scale)
                                        on_release: root.set_deposit_amount(5)
                                    MDRaisedButton:
                                        text: "10"
                                        md_bg_color: SURFACE_SOFT
                                        text_color: TEXT_MAIN
                                        size_hint_y: None
                                        height: dp(42 * root.layout_scale)
                                        on_release: root.set_deposit_amount(10)
                                    MDRaisedButton:
                                        text: "20"
                                        md_bg_color: SURFACE_SOFT
                                        text_color: TEXT_MAIN
                                        size_hint_y: None
                                        height: dp(42 * root.layout_scale)
                                        on_release: root.set_deposit_amount(20)
                                    MDRaisedButton:
                                        text: "50"
                                        md_bg_color: SURFACE_SOFT
                                        text_color: TEXT_MAIN
                                        size_hint_y: None
                                        height: dp(42 * root.layout_scale)
                                        on_release: root.set_deposit_amount(50)
                                    MDRaisedButton:
                                        text: "100"
                                        md_bg_color: SURFACE_SOFT
                                        text_color: TEXT_MAIN
                                        size_hint_y: None
                                        height: dp(42 * root.layout_scale)
                                        on_release: root.set_deposit_amount(100)

                                MDFillRoundFlatIconButton:
                                    text: root.deposit_button_text
                                    icon: "credit-card-check-outline"
                                    md_bg_color: GOLD_SOFT
                                    text_color: BG
                                    size_hint_y: None
                                    height: dp(52 * root.layout_scale)
                                    on_release: root.initiate_deposit()
                                    disabled: root.deposit_busy or not root.deposit_ready

                                MDFillRoundFlatIconButton:
                                    text: "Check Status"
                                    icon: "refresh-circle"
                                    md_bg_color: SURFACE_SOFT
                                    text_color: TEXT_MAIN
                                    size_hint_y: None
                                    height: dp(48 * root.layout_scale)
                                    on_release: root.check_last_deposit_status()

                                MDLabel:
                                    text: ("Reference: " + root.last_paystack_reference) if root.last_paystack_reference else ""
                                    theme_text_color: "Custom"
                                    text_color: GOLD
                                    font_size: sp(11.5 * root.text_scale)
                                    size_hint_y: None
                                    height: self.texture_size[1] if self.text else 0
                                    shorten: True
                                    shorten_from: "right"

                        MDCard:
                            id: deposit_summary_section
                            size_hint_y: None
                            height: deposit_summary_content.height + dp(28 * root.layout_scale) if root.screen_mode == "all" else 0
                            opacity: 1 if root.screen_mode == "all" else 0
                            radius: [dp(20 * root.layout_scale)]
                            md_bg_color: SURFACE
                            elevation: 0
                            padding: [dp(14 * root.layout_scale)] * 4

                            MDBoxLayout:
                                id: deposit_summary_content
                                orientation: "vertical"
                                adaptive_height: True
                                spacing: dp(6 * root.layout_scale)

                                MDLabel:
                                    text: "Summary & Confirmation"
                                    theme_text_color: "Custom"
                                    text_color: GOLD
                                    bold: True

                                MDLabel:
                                    text: root.deposit_summary_text
                                    theme_text_color: "Custom"
                                    text_color: TEXT_SUB
                                    font_size: sp(12 * root.text_scale)
                                    adaptive_height: True

                                MDLabel:
                                    text: root.deposit_due_text
                                    theme_text_color: "Custom"
                                    text_color: TEXT_MAIN
                                    font_size: sp(11.5 * root.text_scale)
                                    adaptive_height: True

                        MDCard:
                            id: withdraw_section
                            size_hint_y: None
                            height: withdraw_section_content.height + dp(28 * root.layout_scale) if root.screen_mode != "deposit" else 0
                            opacity: 1 if root.screen_mode != "deposit" else 0
                            radius: [dp(20 * root.layout_scale)]
                            md_bg_color: SURFACE
                            elevation: 0
                            padding: [dp(14 * root.layout_scale)] * 4

                            MDBoxLayout:
                                id: withdraw_section_content
                                orientation: "vertical"
                                adaptive_height: True
                                spacing: dp(10 * root.layout_scale)

                                MDBoxLayout:
                                    size_hint_y: None
                                    height: dp(40 * root.layout_scale)
                                    spacing: dp(10 * root.layout_scale)

                                    MDCard:
                                        size_hint: None, None
                                        size: dp(34 * root.layout_scale), dp(34 * root.layout_scale)
                                        radius: [dp(11 * root.layout_scale)]
                                        md_bg_color: 0.22, 0.40, 0.32, 1
                                        elevation: 0

                                        MDIconButton:
                                            icon: "cash-minus"
                                            user_font_size: str(18 * root.icon_scale) + "sp"
                                            size_hint: None, None
                                            size: dp(22 * root.layout_scale), dp(22 * root.layout_scale)
                                            pos_hint: {"center_x": 0.5, "center_y": 0.5}
                                            theme_text_color: "Custom"
                                            text_color: TEXT_MAIN
                                            disabled: True

                                    MDLabel:
                                        text: "Withdraw to Agent"
                                        theme_text_color: "Custom"
                                        text_color: GOLD
                                        bold: True
                                        valign: "middle"
                                        shorten: True
                                        shorten_from: "right"

                                    Widget:

                                    MDLabel:
                                        text: "Fee 1%"
                                        theme_text_color: "Custom"
                                        text_color: TEXT_SUB
                                        font_size: sp(11.5 * root.text_scale)
                                        valign: "middle"
                                        halign: "right"

                                MDLabel:
                                    text: "Send funds to an active agent number. We add a 1% fee and show the total before you confirm."
                                    theme_text_color: "Custom"
                                    text_color: TEXT_SUB
                                    font_size: sp(12 * root.text_scale)
                                    adaptive_height: True

                                MDLabel:
                                    text: "Tip: Use the agent's registered 10-digit MoMo number."
                                    theme_text_color: "Custom"
                                    text_color: TEXT_SUB
                                    font_size: sp(11.5 * root.text_scale)
                                    adaptive_height: True

                                MDLabel:
                                    text: "Agent Number"
                                    theme_text_color: "Custom"
                                    text_color: TEXT_MAIN
                                    bold: True
                                    adaptive_height: True

                                MDTextField:
                                    id: transfer_recipient
                                    hint_text: "Agent number, e.g. 0241234567"
                                    mode: "outlined"

                                MDLabel:
                                    text: "Only active agent numbers are supported."
                                    theme_text_color: "Custom"
                                    text_color: TEXT_SUB
                                    font_size: sp(11.5 * root.text_scale)
                                    adaptive_height: True

                                MDLabel:
                                    text: "Withdrawal Amount"
                                    theme_text_color: "Custom"
                                    text_color: TEXT_MAIN
                                    bold: True
                                    adaptive_height: True

                                MDTextField:
                                    id: transfer_amount
                                    hint_text: "Withdrawal amount"
                                    mode: "outlined"
                                    input_filter: "float"
                                    on_text: root.update_withdraw_preview(self.text)

                                MDLabel:
                                    text: "Quick Amounts"
                                    theme_text_color: "Custom"
                                    text_color: TEXT_MAIN
                                    bold: True
                                    adaptive_height: True

                                MDGridLayout:
                                    cols: 2 if root.compact_mode else 4
                                    spacing: dp(6 * root.layout_scale)
                                    size_hint_y: None
                                    height: self.minimum_height

                                    MDRaisedButton:
                                        text: "10"
                                        md_bg_color: SURFACE_SOFT
                                        text_color: TEXT_MAIN
                                        size_hint_y: None
                                        height: dp(42 * root.layout_scale)
                                        on_release: root.set_withdraw_amount(10)
                                    MDRaisedButton:
                                        text: "20"
                                        md_bg_color: SURFACE_SOFT
                                        text_color: TEXT_MAIN
                                        size_hint_y: None
                                        height: dp(42 * root.layout_scale)
                                        on_release: root.set_withdraw_amount(20)
                                    MDRaisedButton:
                                        text: "50"
                                        md_bg_color: SURFACE_SOFT
                                        text_color: TEXT_MAIN
                                        size_hint_y: None
                                        height: dp(42 * root.layout_scale)
                                        on_release: root.set_withdraw_amount(50)
                                    MDRaisedButton:
                                        text: "100"
                                        md_bg_color: SURFACE_SOFT
                                        text_color: TEXT_MAIN
                                        size_hint_y: None
                                        height: dp(42 * root.layout_scale)
                                        on_release: root.set_withdraw_amount(100)

                                MDLabel:
                                    text: root.withdraw_fee_preview
                                    theme_text_color: "Custom"
                                    text_color: TEXT_SUB
                                    font_size: sp(11.5 * root.text_scale)
                                    adaptive_height: True

                                MDLabel:
                                    text: "Your wallet is debited by amount + 1% fee."
                                    theme_text_color: "Custom"
                                    text_color: TEXT_SUB
                                    font_size: sp(11.5 * root.text_scale)
                                    adaptive_height: True

                                MDFillRoundFlatIconButton:
                                    text: "Confirm Withdrawal"
                                    icon: "cash-minus"
                                    md_bg_color: 0.22, 0.40, 0.32, 1
                                    text_color: TEXT_MAIN
                                    size_hint_y: None
                                    height: dp(52 * root.layout_scale)
                                    on_release: root.transfer_funds()
                                    disabled: True if not transfer_recipient.text or not transfer_amount.text else False

                MDBoxLayout:
                    orientation: "vertical"
                    size_hint_y: None
                    height: self.minimum_height if root.screen_mode == "deposit" else 0
                    opacity: 1 if root.screen_mode == "deposit" else 0
                    disabled: True if root.screen_mode != "deposit" else False
                    spacing: dp(12 * root.layout_scale)

                    MDLabel:
                        text: "Quick Actions"
                        theme_text_color: "Custom"
                        text_color: GOLD
                        bold: True
                        adaptive_height: True

                    MDGridLayout:
                        cols: 4
                        spacing: dp(10 * root.layout_scale)
                        size_hint_y: None
                        height: self.minimum_height

                        MDBoxLayout:
                            orientation: "vertical"
                            adaptive_height: True

                            MDIconButton:
                                icon: "pencil-outline"
                                user_font_size: str(26 * root.icon_scale) + "sp"
                                pos_hint: {"center_x": 0.5}
                                theme_text_color: "Custom"
                                text_color: GOLD
                                on_release: root.focus_deposit_amount()

                            MDLabel:
                                text: "Amount"
                                halign: "center"
                                theme_text_color: "Custom"
                                text_color: TEXT_MAIN
                                font_size: sp(11.5 * root.text_scale)
                                adaptive_height: True

                        MDBoxLayout:
                            orientation: "vertical"
                            adaptive_height: True

                            MDIconButton:
                                icon: "refresh-circle"
                                user_font_size: str(26 * root.icon_scale) + "sp"
                                pos_hint: {"center_x": 0.5}
                                theme_text_color: "Custom"
                                text_color: 0.54, 0.82, 0.67, 1
                                on_release: root.check_last_deposit_status()

                            MDLabel:
                                text: "Status"
                                halign: "center"
                                theme_text_color: "Custom"
                                text_color: TEXT_MAIN
                                font_size: sp(11.5 * root.text_scale)
                                adaptive_height: True

                        MDBoxLayout:
                            orientation: "vertical"
                            adaptive_height: True

                            MDIconButton:
                                icon: "history"
                                user_font_size: str(26 * root.icon_scale) + "sp"
                                pos_hint: {"center_x": 0.5}
                                theme_text_color: "Custom"
                                text_color: GOLD_SOFT
                                on_release: root.go_to_transactions()

                            MDLabel:
                                text: "History"
                                halign: "center"
                                theme_text_color: "Custom"
                                text_color: TEXT_MAIN
                                font_size: sp(11.5 * root.text_scale)
                                adaptive_height: True

                        MDBoxLayout:
                            orientation: "vertical"
                            adaptive_height: True

                            MDIconButton:
                                icon: "help-circle-outline"
                                user_font_size: str(26 * root.icon_scale) + "sp"
                                pos_hint: {"center_x": 0.5}
                                theme_text_color: "Custom"
                                text_color: TEXT_SUB
                                on_release: root.show_deposit_help()

                            MDLabel:
                                text: "Help"
                                halign: "center"
                                theme_text_color: "Custom"
                                text_color: TEXT_MAIN
                                font_size: sp(11.5 * root.text_scale)
                                adaptive_height: True

                    MDBoxLayout:
                        adaptive_height: True

                        MDLabel:
                            text: "Recent Activity"
                            theme_text_color: "Custom"
                            text_color: TEXT_MAIN
                            bold: True
                            adaptive_height: True

                        MDTextButton:
                            text: "View All >"
                            theme_text_color: "Custom"
                            text_color: GOLD
                            on_release: root.go_to_transactions()

                    MDCard:
                        radius: [dp(15 * root.layout_scale)]
                        size_hint_y: None
                        height: dp(78 * root.layout_scale)
                        md_bg_color: SURFACE
                        elevation: 0
                        padding: [dp(12 * root.layout_scale)] * 4

                        MDBoxLayout:

                            MDLabel:
                                text: root.recent_activity_left
                                theme_text_color: "Custom"
                                text_color: TEXT_MAIN
                                shorten: True
                                shorten_from: "right"

                            MDLabel:
                                text: root.recent_activity_amount
                                halign: "right"
                                theme_text_color: "Custom"
                                text_color: root.recent_activity_amount_color
                                bold: True
                                shorten: True
                                shorten_from: "right"

                MDBoxLayout:
                    size_hint_y: None
                    height: dp((48 if root.screen_mode == "all" else 44) * root.layout_scale)
                    spacing: dp((8 if root.screen_mode == "all" else 0) * root.layout_scale)

                    MDRaisedButton:
                        text: "Refresh Balance" if root.screen_mode != "all" else "Refresh"
                        size_hint_x: 1
                        on_release: root.load_wallet()

                    MDRaisedButton:
                        text: "History"
                        size_hint_x: 1 if root.screen_mode == "all" else None
                        width: 0 if root.screen_mode != "all" else 1
                        opacity: 1 if root.screen_mode == "all" else 0
                        disabled: True if root.screen_mode != "all" else False
                        on_release:
                            if root.manager: root.manager.current = "transactions"

                MDLabel:
                    text: root.feedback_text
                    size_hint_y: None
                    height: self.texture_size[1] if self.text else 0
                    theme_text_color: "Custom"
                    text_color: root.feedback_color

                Widget:
                    size_hint_y: None
                    height: dp((8 if root.screen_mode == "all" else 0) * root.layout_scale)

        BottomNavBar:
            nav_variant: "default"
            active_target: "wallet"
            layout_scale: root.layout_scale
            text_scale: root.text_scale
            icon_scale: root.icon_scale
"""


class WalletScreen(ActionScreen):
    screen_mode = StringProperty("all")
    page_title = StringProperty("Wallet")
    page_subtitle = StringProperty("Manage wallet funding and withdrawals from one place.")
    balance_display = StringProperty("GHS 0.00")
    wallet_status = StringProperty("Pulling live wallet...")
    greeting_text = StringProperty("Hello")
    last_paystack_reference = StringProperty("")
    deposit_ready = BooleanProperty(False)
    deposit_busy = BooleanProperty(False)
    deposit_button_text = StringProperty("Pay with Paystack")
    deposit_preview = StringProperty("Enter an amount (minimum GHS 1.00).")
    deposit_summary_text = StringProperty(
        "Complete the Paystack payment (in-app or in your browser). Your wallet is credited after confirmation."
    )
    deposit_due_text = StringProperty(
        "Confirmation is automatic. If it delays, tap Check Status and keep your reference."
    )
    withdraw_fee_preview = StringProperty("Enter an amount from GHS 1.00. We will show the fee and total debit.")
    recent_activity_left = StringProperty("No activity\nyet")
    recent_activity_amount = StringProperty("")
    recent_activity_amount_color = ColorProperty([0.74, 0.76, 0.80, 1])
    _verify_sequence = 0

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._dashboard_sequence = 0

    def on_pre_enter(self):
        self.load_wallet()
        amount_field = self.ids.get("transfer_amount")
        self.update_withdraw_preview(amount_field.text if amount_field is not None else "")
        deposit_field = self.ids.get("deposit_amount")
        self.update_deposit_preview(deposit_field.text if deposit_field is not None else "")
        if self.screen_mode == "deposit":
            self._refresh_deposit_dashboard()
        if self.screen_mode in {"all", "deposit"}:
            Clock.schedule_once(lambda _dt: warmup_paystack_checkout(delay_seconds=0.0), 0.25)
        Clock.schedule_once(self._focus_requested_action, 0.1)

    def on_leave(self):
        self._verify_sequence += 1
        self._dashboard_sequence += 1

    @staticmethod
    def _safe_first_name(value: str) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        first = raw.split()[0].strip()
        if not first or first.isdigit():
            return ""
        return first[:24]

    @classmethod
    def _extract_first_name(cls, payload: object) -> str:
        if not isinstance(payload, dict):
            return ""
        first_name = cls._safe_first_name(payload.get("first_name") or "")
        if first_name:
            return first_name
        full_name = cls._safe_first_name(payload.get("full_name") or payload.get("name") or "")
        if full_name:
            return full_name
        return ""

    @staticmethod
    def _friendly_tx_title(tx_type: object) -> str:
        key = str(tx_type or "").strip().lower()
        if key in {"funding", "agent_deposit"}:
            return "Deposit"
        if key == "transfer":
            return "Transfer"
        if key in {"investment_create", "investment_payout"}:
            return "Investment"
        return "Activity"

    @staticmethod
    def _friendly_tx_when(raw_timestamp: object) -> str:
        text = str(raw_timestamp or "").strip()
        if not text:
            return "Recent"
        try:
            cleaned = text[:-1] + "+00:00" if text.endswith("Z") else text
            dt = datetime.fromisoformat(cleaned)
            today = datetime.now(dt.tzinfo).date() if dt.tzinfo else datetime.now().date()
            if dt.date() == today:
                return "Today"
            return dt.strftime("%d %b")
        except Exception:
            return "Recent"

    def _refresh_deposit_dashboard(self) -> None:
        self._dashboard_sequence += 1
        sequence = self._dashboard_sequence
        threading.Thread(target=self._load_deposit_dashboard_worker, args=(sequence,), daemon=True).start()

    def _load_deposit_dashboard_worker(self, sequence: int) -> None:
        greeting_text = "Hello"
        ok, payload = self._request("GET", "/auth/me")
        if ok and isinstance(payload, dict):
            first_name = self._extract_first_name(payload)
            if first_name:
                greeting_text = f"Hello, {first_name}"

        recent_left = "No activity\nyet"
        recent_amount = ""
        recent_color = [0.74, 0.76, 0.80, 1]
        ok, tx_payload = self._request("GET", "/wallet/transactions/me", params={"limit": 1})
        if ok and isinstance(tx_payload, list) and tx_payload:
            tx = tx_payload[0] if isinstance(tx_payload[0], dict) else {}
            title = self._friendly_tx_title(tx.get("type"))
            when = self._friendly_tx_when(tx.get("timestamp") or tx.get("created_at") or "")
            recent_left = f"{title}\n{when}"
            try:
                amount = float(tx.get("amount", 0.0) or 0.0)
            except Exception:
                amount = 0.0
            if abs(amount) > 1e-9:
                sign = "+" if amount >= 0 else "-"
                recent_amount = f"{sign} GHS {abs(amount):,.2f}"
                recent_color = [0.54, 0.82, 0.67, 1] if amount >= 0 else [0.96, 0.47, 0.42, 1]

        Clock.schedule_once(
            lambda _dt: self._apply_deposit_dashboard(sequence, greeting_text, recent_left, recent_amount, recent_color)
        )

    def _apply_deposit_dashboard(
        self,
        sequence: int,
        greeting_text: str,
        recent_left: str,
        recent_amount: str,
        recent_color: list,
    ) -> None:
        if sequence != self._dashboard_sequence:
            return
        self.greeting_text = greeting_text
        self.recent_activity_left = recent_left
        self.recent_activity_amount = recent_amount
        self.recent_activity_amount_color = recent_color

    def focus_deposit_amount(self) -> None:
        field = self.ids.get("deposit_amount")
        if field is not None:
            try:
                field.focus = True
            except Exception:
                pass

        scroll = self.ids.get("content_scroll")
        target = self.ids.get("deposit_section")
        if scroll is not None and target is not None:
            try:
                scroll.scroll_to(target, padding=dp(12 * float(self.layout_scale or 1.0)), animate=False)
            except Exception:
                pass

    def go_to_transactions(self) -> None:
        if self.manager and self.manager.has_screen("transactions"):
            self.manager.current = "transactions"

    def show_deposit_help(self) -> None:
        self._show_popup(
            "Deposit Help",
            "Enter your amount (minimum GHS 1.00) and tap Pay with Paystack. "
            "Complete the payment in-app or in your browser. "
            "Your wallet credits after Paystack confirms. "
            "If it delays, use Check Status with your reference.",
        )

    def _focus_requested_action(self, *_args) -> None:
        app = MDApp.get_running_app()
        action = str(getattr(app, "wallet_entry_action", "") or "").strip().lower()
        if action not in {"deposit", "withdraw"}:
            action = self.screen_mode if self.screen_mode in {"deposit", "withdraw"} else ""
        if action not in {"deposit", "withdraw"}:
            return

        scroll = self.ids.content_scroll
        if self.screen_mode == "all":
            target = self.ids.deposit_section if action == "deposit" else self.ids.withdraw_section
            try:
                scroll.scroll_to(target, padding=dp(12 * self.layout_scale), animate=False)
            except Exception:
                pass
        else:
            scroll.scroll_y = 1

        if action == "withdraw":
            self._set_feedback("Enter the agent number and amount to withdraw.", "info")
        else:
            self._set_feedback("Enter the amount to start your Paystack deposit.", "info")
        app.wallet_entry_action = ""

    @staticmethod
    def _parse_amount(raw_amount: str) -> float:
        try:
            return float(str(raw_amount or "").strip())
        except Exception:
            return 0.0

    def update_withdraw_preview(self, raw_amount: str) -> None:
        amount = self._parse_amount(raw_amount)
        if amount < MIN_WITHDRAW_TO_AGENT_GHS:
            self.withdraw_fee_preview = "Enter an amount from GHS 1.00. A 1% fee is added to the total debit."
            return

        fee = round(amount * 0.01, 2)
        total = round(amount + fee, 2)
        self.withdraw_fee_preview = (
            f"You will send GHS {amount:,.2f}. "
            f"Fee: GHS {fee:,.2f}. "
            f"Total debit: GHS {total:,.2f}."
        )

    def set_withdraw_amount(self, amount: float) -> None:
        field = self.ids.get("transfer_amount")
        if field is None:
            return
        try:
            value = float(amount)
        except Exception:
            return
        if abs(value - int(value)) < 1e-9:
            field.text = str(int(value))
        else:
            field.text = f"{value:.2f}"
        self.update_withdraw_preview(field.text)

    def update_deposit_preview(self, raw_amount: str) -> None:
        amount = self._parse_amount(raw_amount)
        if amount < MIN_PAYSTACK_DEPOSIT_GHS:
            self.deposit_ready = False
            self.deposit_button_text = "Pay with Paystack"
            self.deposit_preview = "Enter an amount (minimum GHS 1.00)."
            return

        self.deposit_ready = True
        self.deposit_button_text = f"Pay GHS {amount:,.2f} with Paystack"
        self.deposit_preview = f"You'll pay GHS {amount:,.2f} via Paystack."

    def set_deposit_amount(self, amount: float) -> None:
        field = self.ids.get("deposit_amount")
        if field is None:
            return
        try:
            value = float(amount)
        except Exception:
            return
        if abs(value - int(value)) < 1e-9:
            field.text = str(int(value))
        else:
            field.text = f"{value:.2f}"
        self.update_deposit_preview(field.text)

    @staticmethod
    def _coerce_wallet_balance(payload: object) -> float | None:
        return WalletScreen._coerce_payload_number(payload, "wallet_balance")

    @staticmethod
    def _coerce_payload_number(payload: object, key: str) -> float | None:
        if not isinstance(payload, dict):
            return None
        raw_value = payload.get(key)
        if raw_value in {None, ""}:
            return None
        try:
            return float(raw_value)
        except Exception:
            return None

    @classmethod
    def _format_paystack_success_message(cls, payload: object, fallback: str = "") -> str:
        credited_amount = cls._coerce_payload_number(payload, "credited_amount")
        wallet_balance = cls._coerce_payload_number(payload, "wallet_balance")
        if credited_amount is not None and wallet_balance is not None:
            return f"GHS {credited_amount:,.2f} credited. New balance: GHS {wallet_balance:,.2f}."
        if credited_amount is not None:
            return f"GHS {credited_amount:,.2f} credited."
        if wallet_balance is not None:
            return f"New balance: GHS {wallet_balance:,.2f}."
        return str(fallback or "").strip() or "Payment successful. Your wallet has been credited instantly."

    def _set_wallet_balance(self, balance: float, status: str = "Live wallet balance") -> None:
        try:
            value = float(balance)
        except Exception:
            return
        self.balance_display = f"GHS {value:,.2f}"
        self.wallet_status = status

    def _refresh_wallet_balance_async(self, status: str = "Live wallet balance") -> None:
        threading.Thread(target=self._refresh_wallet_balance_worker, args=(status,), daemon=True).start()

    def _refresh_wallet_balance_worker(self, status: str) -> None:
        ok, payload = self._request("GET", "/wallet/me")
        if not ok or not isinstance(payload, dict):
            return

        try:
            balance = float(payload.get("balance", 0.0) or 0.0)
        except Exception:
            return

        Clock.schedule_once(lambda _dt, bal=balance, st=status: self._set_wallet_balance(bal, st))

    def load_wallet(self, notify: bool = True):
        ok, payload = self._request("GET", "/wallet/me")
        if ok and isinstance(payload, dict):
            balance = float(payload.get("balance", 0.0) or 0.0)
            self._set_wallet_balance(balance)
            if notify:
                self._set_feedback("Wallet updated.", "success")
            return

        detail = self._extract_detail(payload) or "Unable to load wallet."
        self.wallet_status = "Wallet sync unavailable"
        self._set_feedback(detail, "error")
        self._show_popup("Wallet Sync Error", detail)

    def initiate_deposit(self):
        amount = self._parse_amount(self.ids.deposit_amount.text)
        if amount < MIN_PAYSTACK_DEPOSIT_GHS:
            self._set_feedback("Enter an amount from GHS 1.00 or more.", "error")
            self._show_popup(
                "Invalid Amount",
                "Minimum Paystack deposit is GHS 1.00. Please enter a higher amount.",
            )
            return

        if self.deposit_busy:
            return

        auth_headers = self._auth_headers()
        if not auth_headers:
            self._set_feedback("Please sign in to continue.", "warning")
            self._show_popup("Sign In Required", "Please sign in to continue.")
            return

        warmup_paystack_checkout(delay_seconds=0.0)

        self.deposit_busy = True
        self.deposit_button_text = "Preparing checkout..."
        self._set_feedback("Preparing your Paystack checkout...", "info")
        threading.Thread(target=self._initiate_deposit_worker, args=(amount, auth_headers), daemon=True).start()

    def _initiate_deposit_worker(self, amount: float, headers: dict) -> None:
        result = api_client.request(
            method="POST",
            path="/paystack/initiate",
            payload={"amount": amount},
            headers=headers,
        )
        ok, payload = bool(result.get("ok")), result.get("data", {})
        Clock.schedule_once(lambda _dt: self._handle_initiate_deposit_result(ok, payload))

    def _handle_initiate_deposit_result(self, ok: bool, payload: object) -> None:
        self.deposit_busy = False
        deposit_field = self.ids.get("deposit_amount")
        if deposit_field is not None:
            self.update_deposit_preview(deposit_field.text)

        if ok and isinstance(payload, dict):
            checkout_url = str(payload.get("authorization_url") or "").strip()
            reference = str(payload.get("reference") or "").strip()
            if not checkout_url or not reference:
                self._set_feedback("Unable to start Paystack checkout right now.", "error")
                self._show_popup(
                    "Deposit Failed",
                    "Paystack checkout could not be created. Please try again.",
                )
                return

            opened_in_app = open_paystack_checkout(checkout_url, title="CYBER CASH Paystack", delay_seconds=0.0)
            opened_in_browser = False
            if not opened_in_app:
                try:
                    opened_in_browser = bool(webbrowser.open(checkout_url, new=2))
                except Exception:
                    opened_in_browser = False

            if opened_in_app:
                self._set_feedback(
                    "Opening Paystack checkout in-app. It may take a few seconds on slower devices.",
                    "info",
                )
                self._show_popup(
                    "Complete Payment",
                    "Paystack checkout opens inside the app. If it takes a few seconds to appear, please wait.",
                )
            elif opened_in_browser:
                self._set_feedback("Paystack checkout opened in your browser. Complete payment then return.", "info")
                self._show_popup(
                    "Complete Payment",
                    "Paystack checkout opened in your browser. "
                    "After payment, return to the app. We'll confirm automatically (or tap Check Status).",
                )
            else:
                self._set_feedback("Unable to open Paystack checkout automatically.", "warning")
                self._show_popup(
                    "Open Paystack Checkout",
                    "We couldn't open the Paystack checkout automatically.\n\n"
                    f"Link: {checkout_url}\n"
                    f"Reference: {reference}\n\n"
                    "Please open the link in your browser to complete payment, then come back and tap Check Status.",
                )

            self.last_paystack_reference = reference
            if opened_in_app or opened_in_browser:
                self._start_paystack_verification(reference)
            return

        detail = self._extract_detail(payload) or "Unable to start Paystack deposit."
        self._set_feedback(detail, "error")
        self._show_popup("Deposit Failed", detail)

    def _start_paystack_verification(self, reference: str) -> None:
        self._verify_sequence += 1
        verify_sequence = self._verify_sequence
        threading.Thread(
            target=self._poll_paystack_verification_worker,
            args=(reference, verify_sequence),
            daemon=True,
        ).start()

    def _poll_paystack_verification_worker(self, reference: str, verify_sequence: int) -> None:
        for _ in range(PAYSTACK_VERIFY_MAX_POLLS):
            if verify_sequence != self._verify_sequence:
                return

            time.sleep(PAYSTACK_VERIFY_POLL_INTERVAL_SECONDS)
            ok, payload = self._request("GET", f"/paystack/verify/{reference}")

            if verify_sequence != self._verify_sequence:
                return

            if ok and isinstance(payload, dict):
                status_value = str(payload.get("status", "")).strip().lower()
                message = self._extract_detail(payload) or "Payment verified and wallet credited."

                if status_value == "success":
                    Clock.schedule_once(
                        lambda _dt, msg=message, data=payload: self._on_paystack_success(msg, data)
                    )
                    return

                if status_value in {"pending", "ongoing", "processing", "queued"}:
                    continue

            detail = self._extract_detail(payload)
            detail_lc = detail.lower()
            if "pending" in detail_lc or "processing" in detail_lc or "abandoned" in detail_lc:
                continue

            if detail:
                Clock.schedule_once(lambda _dt, msg=detail: self._on_paystack_failed(msg))
                return

        Clock.schedule_once(lambda _dt: self._on_paystack_timeout(reference))

    def _on_paystack_success(self, message: str, payload: object | None = None) -> None:
        friendly_message = self._format_paystack_success_message(payload, message)
        wallet_balance = self._coerce_wallet_balance(payload)
        if wallet_balance is not None:
            self._set_wallet_balance(wallet_balance, "Wallet credited via Paystack")
        else:
            self.wallet_status = "Wallet credited via Paystack"
            self._refresh_wallet_balance_async("Wallet credited via Paystack")
        self._set_feedback(friendly_message, "success")
        self._show_popup("Deposit Successful", friendly_message)

    def _on_paystack_failed(self, message: str) -> None:
        friendly_message = str(message or "").strip() or "Payment was not completed."
        if "abandoned" in friendly_message.lower():
            pending_message = (
                "Payment is not confirmed yet. If you completed payment, please wait a moment and tap Check Status again. "
                "If you did not complete payment, please start a new deposit to get a new reference."
            )
            self._set_feedback(pending_message, "warning")
            self._show_popup("Still Processing", pending_message)
            return

        self._set_feedback(friendly_message, "error")
        self._show_popup("Deposit Not Completed", friendly_message)

    def _on_paystack_timeout(self, reference: str) -> None:
        self._set_feedback("Still waiting for Paystack confirmation...", "warning")
        self._show_popup(
            "Confirmation Pending",
            "Payment confirmation is taking longer than expected. "
            "If you completed payment, please wait briefly and tap Refresh. "
            f"You can also retry verification with reference: {reference}.",
        )

    def check_last_deposit_status(self) -> None:
        reference = str(self.last_paystack_reference or "").strip()
        if not reference:
            self._set_feedback("Start a Paystack deposit first to get a payment reference.", "warning")
            self._show_popup(
                "No Reference Yet",
                "You have not started a Paystack deposit yet. Enter an amount and tap Pay With Paystack first.",
            )
            return

        self._set_feedback("Checking Paystack payment status...", "info")
        ok, payload = self._request("GET", f"/paystack/verify/{reference}")

        if ok and isinstance(payload, dict):
            status_value = str(payload.get("status", "")).strip().lower()
            message = self._extract_detail(payload) or "Payment status retrieved."

            if status_value == "success":
                self._on_paystack_success(message, payload)
                return

            if status_value in {"pending", "ongoing", "processing", "queued"}:
                self._set_feedback(message, "warning")
                self._show_popup("Still Processing", message)
                return

        detail = self._extract_detail(payload) or "Unable to verify payment status right now."
        detail_lc = detail.lower()
        if "pending" in detail_lc or "processing" in detail_lc or "abandoned" in detail_lc:
            friendly_detail = detail
            if "abandoned" in detail_lc:
                friendly_detail = (
                    "Payment is not confirmed yet. If you completed payment, please wait a moment and tap Check Status again. "
                    "If you did not complete payment, please start a new deposit to get a new reference."
                )
            self._set_feedback(friendly_detail, "warning")
            self._show_popup("Still Processing", friendly_detail)
            return

        self._on_paystack_failed(detail)

    @staticmethod
    def _friendly_withdraw_error(detail: str) -> str:
        message = str(detail or "").strip()
        normalized = message.lower()
        if "not an active registered agent" in normalized:
            return "This number is not an active agent account. Please use the agent's registered number."
        if "recipient user not found" in normalized:
            return "We could not find this number. Enter an active agent's registered number."
        if "recipient_wallet_id" in normalized and (
            "required" in normalized or "valid registered number" in normalized
        ):
            return "Enter a valid 10-digit agent registered number."
        if "minimum withdrawal amount is ghs 1.00" in normalized:
            return "Minimum withdrawal amount is GHS 1.00."
        if "insufficient balance" in normalized:
            return "Insufficient wallet balance for this withdrawal. Amount + 1% fee must be available."
        if "cannot transfer funds to yourself" in normalized:
            return "Please enter a different agent number. You cannot withdraw to your own number."
        return message or "Withdrawal failed. Please try again."

    def transfer_funds(self):
        recipient = normalize_ghana_number(self.ids.transfer_recipient.text.strip())
        amount = self._parse_amount(self.ids.transfer_amount.text)

        if not recipient or len(recipient) != 10:
            self._set_feedback("Enter a valid 10-digit agent registered number.", "error")
            self._show_popup(
                "Invalid Agent Number",
                "Please enter the agent's registered 10-digit Ghana MoMo number.",
            )
            return
        if amount < MIN_WITHDRAW_TO_AGENT_GHS:
            self._set_feedback("Enter an amount from GHS 1.00 or more.", "error")
            self._show_popup("Invalid Amount", "Minimum withdrawal amount is GHS 1.00.")
            return

        estimated_fee = round(amount * 0.01, 2)
        estimated_total = round(amount + estimated_fee, 2)
        self._set_feedback(
            f"Processing withdrawal... Amount: GHS {amount:,.2f}, Fee: GHS {estimated_fee:,.2f}, Total debit: GHS {estimated_total:,.2f}.",
            "info",
        )
        ok, payload = self._request(
            "POST",
            "/wallet/transfer",
            payload={
                "recipient_wallet_id": recipient,
                "amount": amount,
                "currency": "GHS",
                "source_balance": "balance",
                "recipient_must_be_agent": True,
            },
        )
        if ok and isinstance(payload, dict):
            ref = str(payload.get("transfer_reference", "")).strip()
            charged_fee = float(payload.get("transfer_fee", estimated_fee) or 0.0)
            total_debited = float(payload.get("total_debited", estimated_total) or 0.0)
            message = (
                f"Withdrawal successful to {recipient}.\n"
                f"Amount: GHS {amount:,.2f}\n"
                f"Fee (1%): GHS {charged_fee:,.2f}\n"
                f"Total debited: GHS {total_debited:,.2f}"
            )
            if ref:
                message = f"{message}\nRef: {ref}"
            self._set_feedback(message, "success")
            self._show_popup("Withdrawal Successful", message)
            self.ids.transfer_recipient.text = ""
            self.ids.transfer_amount.text = ""
            self.load_wallet()
            return

        detail = self._extract_detail(payload)
        friendly = self._friendly_withdraw_error(detail)
        self._set_feedback(friendly, "error")
        self._show_popup("Withdrawal Failed", friendly)


class DepositScreen(WalletScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.screen_mode = "deposit"
        self.page_title = "Deposit"
        self.page_subtitle = "Add money with Paystack."


class WithdrawScreen(WalletScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.screen_mode = "withdraw"
        self.page_title = "Withdraw"
        self.page_subtitle = "Enter an agent number and amount. We add a 1% fee and show the total before you confirm."


Builder.load_string(KV)
