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
#:set GOLD (0.94, 0.79, 0.46, 1)
#:set TEXT_MAIN (0.95, 0.95, 0.95, 1)
#:set TEXT_SUB (0.74, 0.76, 0.80, 1)

<AdminUsersScreen>:
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
                text: "User Management"
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
                on_release: root.load_users()

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
                            text: "Filters"
                            theme_text_color: "Custom"
                            text_color: app.gold
                            bold: True
                            adaptive_height: True

                        MDTextField:
                            id: search_field
                            hint_text: "Search (name, phone, momo, email)"

                        MDTextField:
                            id: status_field
                            hint_text: "Status (active/suspended) — optional"

                        MDRaisedButton:
                            text: "Apply Filters"
                            on_release: root.load_users()

                MDLabel:
                    text: "Users"
                    theme_text_color: "Custom"
                    text_color: app.gold
                    font_style: "Title"
                    font_size: sp(16.5 * root.text_scale)
                    bold: True
                    adaptive_height: True

                MDBoxLayout:
                    id: user_list
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
            active_target: "admin_users"
            layout_scale: root.layout_scale
            text_scale: root.text_scale
            icon_scale: root.icon_scale
            bar_color: app.ui_surface
            active_color: app.gold
            inactive_color: app.ui_text_secondary
"""


class AdminUsersScreen(ActionScreen):
    summary_text = StringProperty("Loading...")

    def on_pre_enter(self):
        self.load_users()

    def _build_user_card(self, user: dict) -> MDCard:
        layout_scale = float(self.layout_scale or 1.0)
        text_scale = float(self.text_scale or 1.0)

        user_id = int(user.get("id", 0) or 0)
        name = str(user.get("full_name", "") or "").strip()
        phone = str(user.get("momo_number") or user.get("phone_number") or "").strip()
        role = str(user.get("role", "") or "").strip() or ("admin" if bool(user.get("is_admin")) else "user")
        status = str(user.get("status", "") or "").strip().lower()
        if not status:
            status = "active" if bool(user.get("is_active", True)) else "suspended"

        flags = []
        if bool(user.get("is_admin")):
            flags.append("Admin")
        if bool(user.get("is_agent")):
            flags.append("Agent")
        if bool(user.get("is_verified")):
            flags.append("Verified")
        if not bool(user.get("is_active", True)):
            flags.append("Inactive")
        flag_text = " | ".join(flags) if flags else "—"

        card = MDCard(
            size_hint_y=None,
            height=dp(154 * layout_scale),
            radius=[dp(16 * layout_scale)],
            md_bg_color=[0.08, 0.10, 0.14, 0.95],
            elevation=0,
            padding=[dp(12 * layout_scale), dp(10 * layout_scale), dp(12 * layout_scale), dp(10 * layout_scale)],
        )

        content = MDBoxLayout(orientation="vertical", spacing=dp(6 * layout_scale))
        header = MDBoxLayout(orientation="horizontal", spacing=dp(8 * layout_scale))
        header.add_widget(
            MDLabel(
                text=f"User #{user_id}",
                theme_text_color="Custom",
                text_color=[0.95, 0.95, 0.95, 1],
                bold=True,
                font_size=f"{15.5 * text_scale:.1f}sp",
            )
        )
        header.add_widget(
            MDLabel(
                text=f"{role.upper()} • {status.upper()}",
                theme_text_color="Custom",
                text_color=[0.94, 0.79, 0.46, 1],
                halign="right",
                bold=True,
                font_size=f"{11.5 * text_scale:.1f}sp",
                size_hint_x=None,
                width=dp(170 * layout_scale),
            )
        )
        content.add_widget(header)
        content.add_widget(
            MDLabel(
                text=f"{name or '—'}   |   {phone or '—'}",
                theme_text_color="Custom",
                text_color=[0.74, 0.76, 0.80, 1],
                font_size=f"{11.5 * text_scale:.1f}sp",
            )
        )
        content.add_widget(
            MDLabel(
                text=f"Flags: {flag_text}",
                theme_text_color="Custom",
                text_color=[0.74, 0.76, 0.80, 1],
                font_size=f"{11.0 * text_scale:.1f}sp",
            )
        )

        actions = MDBoxLayout(orientation="horizontal", spacing=dp(10 * layout_scale), size_hint_y=None, height=dp(44 * layout_scale))
        actions.add_widget(
            MDRaisedButton(
                text="Suspend",
                md_bg_color=[0.96, 0.47, 0.42, 1],
                disabled=status == "suspended",
                on_release=lambda _btn, uid=user_id: self.update_user_status(uid, "suspended"),
            )
        )
        actions.add_widget(
            MDRaisedButton(
                text="Activate",
                md_bg_color=[0.54, 0.82, 0.67, 1],
                disabled=status == "active",
                on_release=lambda _btn, uid=user_id: self.update_user_status(uid, "active"),
            )
        )
        content.add_widget(actions)

        card.add_widget(content)
        return card

    def load_users(self) -> None:
        self._set_feedback("Loading users...", "info")
        q = str(getattr(self.ids.search_field, "text", "") or "").strip()
        status = str(getattr(self.ids.status_field, "text", "") or "").strip().lower()

        params = {"limit": 50, "offset": 0}
        if q:
            params["q"] = q
        if status in {"active", "suspended"}:
            params["status"] = status

        ok, payload = self._request("GET", "/admin/users", params=params)
        container = self.ids.user_list
        container.clear_widgets()

        if ok and isinstance(payload, list):
            self.summary_text = f"{len(payload)} user(s)"
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
                        text="No users found.",
                        theme_text_color="Custom",
                        text_color=[0.74, 0.76, 0.80, 1],
                        halign="center",
                    )
                )
                container.add_widget(empty)
                self._set_feedback("No users found.", "warning")
                return

            for user in payload[:80]:
                if isinstance(user, dict):
                    container.add_widget(self._build_user_card(user))
            self._set_feedback("Users loaded.", "success")
            return

        detail = self._extract_detail(payload) or "Unable to load users."
        self.summary_text = "Sync failed"
        self._set_feedback(detail, "error")
        self._show_popup("Users", detail)

    def update_user_status(self, user_id: int, new_status: str) -> None:
        status_value = str(new_status or "").strip().lower()
        if status_value not in {"active", "suspended"}:
            self._show_popup("User Status", "Invalid status value.")
            return

        self._set_feedback("Updating user status...", "info")
        ok, payload = self._request(
            "PUT",
            f"/admin/users/{int(user_id)}/status",
            payload={"status": status_value},
        )
        if ok:
            self._set_feedback("User updated.", "success")
            self.load_users()
            return
        detail = self._extract_detail(payload) or "Unable to update user."
        self._set_feedback(detail, "error")
        self._show_popup("User Status", detail)


Builder.load_string(KV)
