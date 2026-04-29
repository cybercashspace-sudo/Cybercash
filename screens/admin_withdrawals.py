from __future__ import annotations

import json

from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import StringProperty
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDRaisedButton
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel

from core.screen_actions import ActionScreen

KV = """
#:import dp kivy.metrics.dp
#:import sp kivy.metrics.sp
#:set BG (0.03, 0.04, 0.06, 1)
#:set SURFACE (0.08, 0.10, 0.14, 0.95)
#:set GOLD (0.94, 0.79, 0.46, 1)
#:set TEXT_MAIN (0.95, 0.95, 0.95, 1)
#:set TEXT_SUB (0.74, 0.76, 0.80, 1)

<AdminWithdrawalsScreen>:
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
                text: "Approve Withdrawals"
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

        MDBoxLayout:
            size_hint_y: None
            height: dp(44 * root.layout_scale)
            padding: [dp(16 * root.layout_scale), 0, dp(16 * root.layout_scale), 0]
            spacing: dp(8 * root.layout_scale)

            MDRaisedButton:
                text: "Refresh"
                on_release: root.load_withdrawals()

            MDLabel:
                text: root.summary_text
                halign: "right"
                theme_text_color: "Custom"
                text_color: app.ui_text_secondary

        ScrollView:
            do_scroll_x: False
            bar_width: 0

            MDBoxLayout:
                orientation: "vertical"
                adaptive_height: True
                padding: [dp(16 * root.layout_scale), dp(10 * root.layout_scale), dp(16 * root.layout_scale), dp(16 * root.layout_scale)]
                spacing: dp(12 * root.layout_scale)

                MDLabel:
                    text: "Fiat Withdrawals (MoMo)"
                    theme_text_color: "Custom"
                    text_color: app.gold
                    font_style: "Title"
                    font_size: sp(16.5 * root.text_scale)
                    bold: True
                    adaptive_height: True

                MDBoxLayout:
                    id: fiat_list
                    orientation: "vertical"
                    adaptive_height: True
                    spacing: dp(10 * root.layout_scale)

                MDLabel:
                    text: "Crypto Withdrawals"
                    theme_text_color: "Custom"
                    text_color: app.gold
                    font_style: "Title"
                    font_size: sp(16.5 * root.text_scale)
                    bold: True
                    adaptive_height: True

                MDBoxLayout:
                    id: crypto_list
                    orientation: "vertical"
                    adaptive_height: True
                    spacing: dp(10 * root.layout_scale)

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


class AdminWithdrawalsScreen(ActionScreen):
    summary_text = StringProperty("Loading...")

    def on_pre_enter(self):
        self.load_withdrawals()

    @staticmethod
    def _parse_metadata(raw_metadata: object) -> dict:
        if isinstance(raw_metadata, dict):
            return raw_metadata
        if isinstance(raw_metadata, str) and raw_metadata.strip():
            try:
                parsed = json.loads(raw_metadata)
                return parsed if isinstance(parsed, dict) else {}
            except Exception:
                return {}
        return {}

    @staticmethod
    def _format_ghs(value: object) -> str:
        try:
            amount = float(value or 0.0)
        except Exception:
            amount = 0.0
        return f"GHS {amount:,.2f}"

    @staticmethod
    def _format_coin(value: object, coin: str = "") -> str:
        try:
            amount = float(value or 0.0)
        except Exception:
            amount = 0.0
        symbol = str(coin or "").strip().upper()
        if symbol:
            return f"{amount:,.6f} {symbol}"
        return f"{amount:,.6f}"

    def _build_action_row(self, on_approve, on_reject) -> MDBoxLayout:
        layout_scale = float(self.layout_scale or 1.0)
        row = MDBoxLayout(orientation="horizontal", spacing=dp(10 * layout_scale), size_hint_y=None, height=dp(44 * layout_scale))
        row.add_widget(
            MDRaisedButton(
                text="Approve",
                md_bg_color=[0.54, 0.82, 0.67, 1],
                on_release=on_approve,
            )
        )
        row.add_widget(
            MDRaisedButton(
                text="Reject",
                md_bg_color=[0.96, 0.47, 0.42, 1],
                on_release=on_reject,
            )
        )
        return row

    def _build_fiat_card(self, payment: dict) -> MDCard:
        layout_scale = float(self.layout_scale or 1.0)
        text_scale = float(self.text_scale or 1.0)

        payment_id = int(payment.get("id", 0) or 0)
        user_id = int(payment.get("user_id", 0) or 0)
        amount = payment.get("amount", 0.0)
        currency = str(payment.get("currency", "GHS") or "GHS").upper()
        status = str(payment.get("status", "") or "").strip()
        meta = self._parse_metadata(payment.get("metadata_json"))
        phone = str(meta.get("phone_number", "") or "").strip()
        network = str(meta.get("network", "") or "").strip()

        card = MDCard(
            size_hint_y=None,
            height=dp(132 * layout_scale),
            radius=[dp(16 * layout_scale)],
            md_bg_color=[0.08, 0.10, 0.14, 0.95],
            elevation=0,
            padding=[dp(12 * layout_scale), dp(10 * layout_scale), dp(12 * layout_scale), dp(10 * layout_scale)],
        )
        content = MDBoxLayout(orientation="vertical", spacing=dp(6 * layout_scale))
        header = MDBoxLayout(orientation="horizontal", spacing=dp(8 * layout_scale))
        header.add_widget(
            MDLabel(
                text=f"Fiat Withdrawal #{payment_id}",
                theme_text_color="Custom",
                text_color=[0.95, 0.95, 0.95, 1],
                bold=True,
                font_size=f"{15.5 * text_scale:.1f}sp",
            )
        )
        header.add_widget(
            MDLabel(
                text=self._format_ghs(amount) if currency == "GHS" else f"{float(amount or 0.0):,.2f} {currency}",
                theme_text_color="Custom",
                text_color=[0.94, 0.79, 0.46, 1],
                halign="right",
                bold=True,
                font_size=f"{14.5 * text_scale:.1f}sp",
                size_hint_x=None,
                width=dp(150 * layout_scale),
            )
        )
        content.add_widget(header)
        content.add_widget(
            MDLabel(
                text=f"User ID: {user_id}   Status: {status or 'pending'}",
                theme_text_color="Custom",
                text_color=[0.74, 0.76, 0.80, 1],
                font_size=f"{11.5 * text_scale:.1f}sp",
            )
        )
        if phone or network:
            content.add_widget(
                MDLabel(
                    text=f"MoMo: {phone or '—'}   Network: {network or '—'}",
                    theme_text_color="Custom",
                    text_color=[0.74, 0.76, 0.80, 1],
                    font_size=f"{11.5 * text_scale:.1f}sp",
                )
            )

        content.add_widget(
            self._build_action_row(
                on_approve=lambda _btn, pid=payment_id: self._decide_fiat(pid, "approved"),
                on_reject=lambda _btn, pid=payment_id: self._decide_fiat(pid, "rejected"),
            )
        )
        card.add_widget(content)
        return card

    def _build_crypto_card(self, tx: dict) -> MDCard:
        layout_scale = float(self.layout_scale or 1.0)
        text_scale = float(self.text_scale or 1.0)

        tx_id = int(tx.get("id", 0) or 0)
        user_id = int(tx.get("user_id", 0) or 0)
        amount = tx.get("amount", 0.0)
        coin = str(tx.get("coin_type", "") or "").strip().upper()
        status = str(tx.get("status", "") or "").strip()
        to_address = str(tx.get("to_address", "") or "").strip()

        card = MDCard(
            size_hint_y=None,
            height=dp(146 * layout_scale),
            radius=[dp(16 * layout_scale)],
            md_bg_color=[0.08, 0.10, 0.14, 0.95],
            elevation=0,
            padding=[dp(12 * layout_scale), dp(10 * layout_scale), dp(12 * layout_scale), dp(10 * layout_scale)],
        )
        content = MDBoxLayout(orientation="vertical", spacing=dp(6 * layout_scale))
        header = MDBoxLayout(orientation="horizontal", spacing=dp(8 * layout_scale))
        header.add_widget(
            MDLabel(
                text=f"Crypto Withdrawal #{tx_id}",
                theme_text_color="Custom",
                text_color=[0.95, 0.95, 0.95, 1],
                bold=True,
                font_size=f"{15.5 * text_scale:.1f}sp",
            )
        )
        header.add_widget(
            MDLabel(
                text=self._format_coin(amount, coin),
                theme_text_color="Custom",
                text_color=[0.94, 0.79, 0.46, 1],
                halign="right",
                bold=True,
                font_size=f"{14.0 * text_scale:.1f}sp",
                size_hint_x=None,
                width=dp(160 * layout_scale),
            )
        )
        content.add_widget(header)
        content.add_widget(
            MDLabel(
                text=f"User ID: {user_id}   Status: {status or 'pending'}",
                theme_text_color="Custom",
                text_color=[0.74, 0.76, 0.80, 1],
                font_size=f"{11.5 * text_scale:.1f}sp",
            )
        )
        if to_address:
            content.add_widget(
                MDLabel(
                    text=f"To: {to_address[:28]}{'…' if len(to_address) > 28 else ''}",
                    theme_text_color="Custom",
                    text_color=[0.74, 0.76, 0.80, 1],
                    font_size=f"{11.5 * text_scale:.1f}sp",
                )
            )

        content.add_widget(
            self._build_action_row(
                on_approve=lambda _btn, tid=tx_id: self._decide_crypto(tid, "approved"),
                on_reject=lambda _btn, tid=tx_id: self._decide_crypto(tid, "rejected"),
            )
        )
        card.add_widget(content)
        return card

    def _decide_fiat(self, payment_id: int, decision: str) -> None:
        self._set_feedback("Updating withdrawal decision...", "info")
        ok, payload = self._request(
            "PUT",
            f"/admin/withdrawals/fiat/{int(payment_id)}/approve-reject",
            payload={"status": str(decision)},
        )
        if ok:
            self._set_feedback("Fiat withdrawal updated.", "success")
            self.load_withdrawals(silent=True)
            return
        detail = self._extract_detail(payload) or "Unable to update fiat withdrawal."
        self._set_feedback(detail, "error")
        self._show_popup("Withdrawal Approval", detail)

    def _decide_crypto(self, crypto_tx_id: int, decision: str) -> None:
        self._set_feedback("Updating withdrawal decision...", "info")
        ok, payload = self._request(
            "PUT",
            f"/admin/withdrawals/crypto/{int(crypto_tx_id)}/approve-reject",
            payload={"status": str(decision)},
        )
        if ok:
            self._set_feedback("Crypto withdrawal updated.", "success")
            self.load_withdrawals(silent=True)
            return
        detail = self._extract_detail(payload) or "Unable to update crypto withdrawal."
        self._set_feedback(detail, "error")
        self._show_popup("Withdrawal Approval", detail)

    def load_withdrawals(self, *, silent: bool = False) -> None:
        if not silent:
            self._set_feedback("Loading pending withdrawals...", "info")

        ok_fiat, fiat_payload = self._request("GET", "/admin/withdrawals/fiat")
        ok_crypto, crypto_payload = self._request("GET", "/admin/withdrawals/crypto")

        fiat_list = self.ids.fiat_list
        crypto_list = self.ids.crypto_list
        fiat_list.clear_widgets()
        crypto_list.clear_widgets()

        fiat_items = fiat_payload if ok_fiat and isinstance(fiat_payload, list) else []
        crypto_items = crypto_payload if ok_crypto and isinstance(crypto_payload, list) else []

        self.summary_text = f"Fiat {len(fiat_items)} | Crypto {len(crypto_items)}"

        if fiat_items:
            for item in fiat_items[:50]:
                fiat_list.add_widget(self._build_fiat_card(item))
        else:
            fiat_list.add_widget(
                MDCard(
                    size_hint_y=None,
                    height=dp(62 * float(self.layout_scale or 1.0)),
                    radius=[dp(14 * float(self.layout_scale or 1.0))],
                    md_bg_color=list([0.08, 0.10, 0.14, 0.95]),
                    elevation=0,
                    padding=[dp(12 * float(self.layout_scale or 1.0))] * 4,
                )
            )
            fiat_list.children[0].add_widget(
                MDLabel(
                    text="No pending fiat withdrawals.",
                    theme_text_color="Custom",
                    text_color=[0.74, 0.76, 0.80, 1],
                    halign="center",
                )
            )

        if crypto_items:
            for item in crypto_items[:50]:
                crypto_list.add_widget(self._build_crypto_card(item))
        else:
            crypto_list.add_widget(
                MDCard(
                    size_hint_y=None,
                    height=dp(62 * float(self.layout_scale or 1.0)),
                    radius=[dp(14 * float(self.layout_scale or 1.0))],
                    md_bg_color=list([0.08, 0.10, 0.14, 0.95]),
                    elevation=0,
                    padding=[dp(12 * float(self.layout_scale or 1.0))] * 4,
                )
            )
            crypto_list.children[0].add_widget(
                MDLabel(
                    text="No pending crypto withdrawals.",
                    theme_text_color="Custom",
                    text_color=[0.74, 0.76, 0.80, 1],
                    halign="center",
                )
            )

        if not silent:
            if (ok_fiat or ok_crypto) and (fiat_items or crypto_items):
                self._set_feedback("Withdrawals loaded.", "success")
            elif ok_fiat and ok_crypto:
                self._set_feedback("No pending withdrawals.", "warning")
            else:
                detail = self._extract_detail(fiat_payload if not ok_fiat else crypto_payload) or "Unable to load withdrawals."
                self._set_feedback(detail, "error")
                self._show_popup("Withdrawals", detail)


Builder.load_string(KV)
