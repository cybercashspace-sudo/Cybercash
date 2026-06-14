import json
import os
import threading
import time
import webbrowser
from datetime import datetime, timezone

import requests
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.metrics import dp, sp
from kivy.properties import BooleanProperty, NumericProperty, StringProperty
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.gridlayout import GridLayout
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDIconButton
from kivymd.uix.card import MDCard
from kivymd.uix.fitimage import FitImage
from kivymd.uix.label import MDLabel
from kivymd.uix.screen import MDScreen

from api.client import API_URL, api_client
from core.bottom_nav import BottomNavBar
from core.message_sanitizer import extract_backend_message, sanitize_backend_message
from core.paystack_checkout import open_paystack_checkout, warmup_paystack_checkout
from core.popup_manager import show_confirm_dialog, show_custom_dialog, show_message_dialog

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
