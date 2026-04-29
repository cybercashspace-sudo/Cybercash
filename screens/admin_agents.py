from __future__ import annotations

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
#:set SURFACE_SOFT (0.12, 0.14, 0.18, 0.95)
#:set GOLD (0.94, 0.79, 0.46, 1)
#:set TEXT_MAIN (0.95, 0.95, 0.95, 1)
#:set TEXT_SUB (0.74, 0.76, 0.80, 1)

<AdminAgentsScreen>:
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
                text: "Agent Management"
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
                on_release: root.load_agents()

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

                MDCard:
                    md_bg_color: app.ui_surface
                    radius: [dp(18 * root.layout_scale)]
                    elevation: 0
                    padding: [dp(12 * root.layout_scale)] * 4
                    adaptive_height: True

                    MDBoxLayout:
                        orientation: "vertical"
                        adaptive_height: True
                        spacing: dp(8 * root.layout_scale)

                        MDLabel:
                            text: "Update Commission Rate"
                            theme_text_color: "Custom"
                            text_color: app.gold
                            bold: True
                            adaptive_height: True

                        MDBoxLayout:
                            adaptive_height: True
                            spacing: dp(10 * root.layout_scale)

                            MDTextField:
                                id: agent_id_field
                                hint_text: "Agent ID"
                                input_filter: "int"

                            MDTextField:
                                id: commission_field
                                hint_text: "Commission (e.g. 0.02)"

                        MDRaisedButton:
                            text: "Apply Commission"
                            on_release: root.apply_commission()

                MDLabel:
                    text: "Agents"
                    theme_text_color: "Custom"
                    text_color: app.gold
                    font_style: "Title"
                    font_size: sp(16.5 * root.text_scale)
                    bold: True
                    adaptive_height: True

                MDBoxLayout:
                    id: agent_list
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


class AdminAgentsScreen(ActionScreen):
    summary_text = StringProperty("Loading...")

    def on_pre_enter(self):
        self.load_agents()

    @staticmethod
    def _format_ghs(value: object) -> str:
        try:
            amount = float(value or 0.0)
        except Exception:
            amount = 0.0
        return f"GHS {amount:,.2f}"

    def _build_agent_card(self, agent: dict) -> MDCard:
        layout_scale = float(self.layout_scale or 1.0)
        text_scale = float(self.text_scale or 1.0)

        agent_id = int(agent.get("id", 0) or 0)
        user_id = int(agent.get("user_id", 0) or 0)
        status = str(agent.get("status", "") or "").strip()
        business_name = str(agent.get("business_name", "") or "").strip()
        location = str(agent.get("agent_location", "") or "").strip()
        commission_rate = float(agent.get("commission_rate", 0.0) or 0.0)
        float_balance = agent.get("float_balance", 0.0)
        commission_balance = agent.get("commission_balance", 0.0)
        borrowing_frozen = bool(agent.get("is_borrowing_frozen", False))

        user = agent.get("user") if isinstance(agent.get("user"), dict) else {}
        name = str((user or {}).get("full_name", "") or "").strip()
        phone = str((user or {}).get("momo_number") or (user or {}).get("phone_number") or "").strip()

        card = MDCard(
            size_hint_y=None,
            height=dp(176 * layout_scale),
            radius=[dp(16 * layout_scale)],
            md_bg_color=[0.08, 0.10, 0.14, 0.95],
            elevation=0,
            padding=[dp(12 * layout_scale), dp(10 * layout_scale), dp(12 * layout_scale), dp(10 * layout_scale)],
        )

        content = MDBoxLayout(orientation="vertical", spacing=dp(6 * layout_scale))
        header = MDBoxLayout(orientation="horizontal", spacing=dp(8 * layout_scale))
        header.add_widget(
            MDLabel(
                text=f"Agent #{agent_id}   (User {user_id})",
                theme_text_color="Custom",
                text_color=[0.95, 0.95, 0.95, 1],
                bold=True,
                font_size=f"{15.5 * text_scale:.1f}sp",
            )
        )
        header.add_widget(
            MDLabel(
                text=(status or "pending").upper(),
                theme_text_color="Custom",
                text_color=[0.94, 0.79, 0.46, 1],
                halign="right",
                bold=True,
                font_size=f"{12.0 * text_scale:.1f}sp",
                size_hint_x=None,
                width=dp(120 * layout_scale),
            )
        )
        content.add_widget(header)

        if name or phone:
            content.add_widget(
                MDLabel(
                    text=f"{name or '—'}   |   {phone or '—'}",
                    theme_text_color="Custom",
                    text_color=[0.74, 0.76, 0.80, 1],
                    font_size=f"{11.5 * text_scale:.1f}sp",
                )
            )
        if business_name or location:
            content.add_widget(
                MDLabel(
                    text=f"{business_name or '—'}   |   {location or '—'}",
                    theme_text_color="Custom",
                    text_color=[0.74, 0.76, 0.80, 1],
                    font_size=f"{11.5 * text_scale:.1f}sp",
                )
            )

        content.add_widget(
            MDLabel(
                text=(
                    f"Commission: {commission_rate * 100:.2f}%   |   "
                    f"Float: {self._format_ghs(float_balance)}   |   "
                    f"Earned: {self._format_ghs(commission_balance)}"
                ),
                theme_text_color="Custom",
                text_color=[0.74, 0.76, 0.80, 1],
                font_size=f"{11.0 * text_scale:.1f}sp",
            )
        )
        content.add_widget(
            MDLabel(
                text=f"Borrowing frozen: {'Yes' if borrowing_frozen else 'No'}",
                theme_text_color="Custom",
                text_color=[0.74, 0.76, 0.80, 1],
                font_size=f"{11.0 * text_scale:.1f}sp",
            )
        )

        actions = MDBoxLayout(orientation="horizontal", spacing=dp(10 * layout_scale), size_hint_y=None, height=dp(44 * layout_scale))
        if (status or "").lower() != "active":
            actions.add_widget(
                MDRaisedButton(
                    text="Approve",
                    md_bg_color=[0.54, 0.82, 0.67, 1],
                    on_release=lambda _btn, aid=agent_id: self.approve_agent(aid),
                )
            )
        else:
            actions.add_widget(
                MDRaisedButton(
                    text="Approved",
                    disabled=True,
                )
            )
        actions.add_widget(
            MDRaisedButton(
                text="Unfreeze" if borrowing_frozen else "Freeze",
                md_bg_color=[0.94, 0.79, 0.46, 1],
                on_release=lambda _btn, aid=agent_id, frozen=borrowing_frozen: self.toggle_borrowing_freeze(aid, frozen),
            )
        )
        content.add_widget(actions)

        card.add_widget(content)
        return card

    def load_agents(self) -> None:
        self._set_feedback("Loading agents...", "info")
        ok, payload = self._request("GET", "/admin/agents")

        container = self.ids.agent_list
        container.clear_widgets()

        if ok and isinstance(payload, list):
            self.summary_text = f"{len(payload)} agent(s)"
            if not payload:
                empty = MDCard(
                    size_hint_y=None,
                    height=dp(62 * float(self.layout_scale or 1.0)),
                    radius=[dp(14 * float(self.layout_scale or 1.0))],
                    md_bg_color=[0.08, 0.10, 0.14, 0.95],
                    elevation=0,
                )
                empty.add_widget(
                    MDLabel(
                        text="No agents found.",
                        theme_text_color="Custom",
                        text_color=[0.74, 0.76, 0.80, 1],
                        halign="center",
                    )
                )
                container.add_widget(empty)
                self._set_feedback("No agents found.", "warning")
                return

            for agent in payload[:80]:
                container.add_widget(self._build_agent_card(agent))
            self._set_feedback("Agents loaded.", "success")
            return

        detail = self._extract_detail(payload) or "Unable to load agents."
        self.summary_text = "Sync failed"
        self._set_feedback(detail, "error")
        self._show_popup("Agents", detail)

    def approve_agent(self, agent_id: int) -> None:
        self._set_feedback("Approving agent...", "info")
        ok, payload = self._request("PUT", f"/admin/agents/{int(agent_id)}/approve")
        if ok:
            self._set_feedback("Agent approved.", "success")
            self.load_agents()
            return
        detail = self._extract_detail(payload) or "Unable to approve agent."
        self._set_feedback(detail, "error")
        self._show_popup("Agent Approval", detail)

    def toggle_borrowing_freeze(self, agent_id: int, currently_frozen: bool) -> None:
        decision = not bool(currently_frozen)
        self._set_feedback("Updating agent controls...", "info")
        ok, payload = self._request(
            "PUT",
            f"/admin/agents/{int(agent_id)}/freeze-borrowing",
            payload={"is_borrowing_frozen": decision},
        )
        if ok:
            self._set_feedback("Agent updated.", "success")
            self.load_agents()
            return
        detail = self._extract_detail(payload) or "Unable to update agent."
        self._set_feedback(detail, "error")
        self._show_popup("Agent Controls", detail)

    def apply_commission(self) -> None:
        agent_id_raw = str(getattr(self.ids.agent_id_field, "text", "") or "").strip()
        commission_raw = str(getattr(self.ids.commission_field, "text", "") or "").strip()
        if not agent_id_raw.isdigit():
            self._show_popup("Commission Update", "Enter a valid Agent ID.")
            return
        try:
            commission_rate = float(commission_raw)
        except Exception:
            self._show_popup("Commission Update", "Enter a valid commission rate (e.g. 0.02).")
            return

        if not (0 <= commission_rate <= 1):
            self._show_popup("Commission Update", "Commission rate must be between 0 and 1.")
            return

        agent_id = int(agent_id_raw)
        self._set_feedback("Updating commission rate...", "info")
        ok, payload = self._request(
            "PUT",
            f"/admin/agents/{agent_id}/commission",
            params={"commission_rate": commission_rate},
        )
        if ok:
            self._set_feedback("Commission updated.", "success")
            self.ids.agent_id_field.text = ""
            self.ids.commission_field.text = ""
            self.load_agents()
            return
        detail = self._extract_detail(payload) or "Unable to update commission."
        self._set_feedback(detail, "error")
        self._show_popup("Commission Update", detail)


Builder.load_string(KV)
