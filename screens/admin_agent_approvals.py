from __future__ import annotations

import base64
import io
import threading

from kivy.clock import Clock
from kivy.core.image import Image as CoreImage
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import BooleanProperty, StringProperty
from kivy.uix.image import Image
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDRaisedButton
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel

from core.popup_manager import show_confirm_dialog, show_custom_dialog
from core.screen_actions import ActionScreen


KV = """
#:import dp kivy.metrics.dp
#:import sp kivy.metrics.sp
<AdminAgentApprovalsScreen>:
    MDBoxLayout:
        orientation: "vertical"
        md_bg_color: app.ui_background

        MDBoxLayout:
            size_hint_y: None
            height: dp(58 * root.layout_scale)
            padding: [dp(16), dp(8), dp(16), 0]
            MDLabel:
                text: "Agent onboarding approvals"
                font_style: "Title"
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
            height: dp(48)
            padding: [dp(16), 0, dp(16), 0]
            MDRaisedButton:
                text: "Refresh"
                disabled: root.loading
                on_release: root.load_pending()
            MDLabel:
                text: root.summary_text
                halign: "right"
                theme_text_color: "Secondary"

        PullRefreshScrollView:
            root_layout: root
            refresh_callback: root.pull_to_refresh
            spinner_color: app.gold
            circle_color: app.ui_background
            do_scroll_x: False
            bar_width: 0
            MDBoxLayout:
                id: request_list
                orientation: "vertical"
                adaptive_height: True
                padding: [dp(16), dp(12), dp(16), dp(20)]
                spacing: dp(10)

        MDLabel:
            text: root.feedback_text
            theme_text_color: "Custom"
            text_color: root.feedback_color
            adaptive_height: True
            padding: [dp(16), 0, dp(16), dp(4)]

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

Builder.load_string(KV)


class AdminAgentApprovalsScreen(ActionScreen):
    loading = BooleanProperty(False)
    summary_text = StringProperty("Waiting for requests")

    def __init__(self, **kwargs):
        self._approval_request_generation = 0
        self._current_review_agent_id = None
        super().__init__(**kwargs)

    def on_pre_enter(self, *_args):
        self.load_pending()

    def load_pending(self):
        if self.loading:
            return
        self.loading = True
        self._set_feedback("Loading pending identity reviews…", "info")
        threading.Thread(target=self._pending_worker, daemon=True).start()

    def _pending_worker(self):
        result = self._request("GET", "/admin/agents/kyc-pending", timeout=(4, 18))
        Clock.schedule_once(lambda _dt, response=result: self._apply_pending(response))

    def _apply_pending(self, result):
        self.loading = False
        container = self.ids.request_list
        container.clear_widgets()
        ok, payload = result
        if not ok or not isinstance(payload, list):
            self.summary_text = "Could not load requests"
            self._set_feedback(self._extract_detail(payload) or "Unable to load pending identity reviews.", "error")
            return
        self.summary_text = f"{len(payload)} pending"
        if not payload:
            container.add_widget(MDLabel(text="No agent identity reviews are waiting.", adaptive_height=True))
            self._set_feedback("All caught up.", "info")
            return
        for request in payload[:100]:
            agent_id = int(request.get("agent_id") or 0)
            card = MDCard(
                size_hint_y=None,
                height=dp(112 * self.layout_scale),
                radius=[dp(16 * self.layout_scale)],
                md_bg_color=[0.08, 0.10, 0.14, 0.98],
                elevation=0,
                padding=dp(12 * self.layout_scale),
            )
            row = MDBoxLayout(orientation="horizontal", spacing=dp(10 * self.layout_scale))
            details = MDBoxLayout(orientation="vertical", spacing=dp(4 * self.layout_scale))
            details.add_widget(MDLabel(text=f"Agent request #{agent_id}", bold=True, adaptive_height=True))
            details.add_widget(MDLabel(text=f"User #{int(request.get('user_id') or 0)} · Identity pending review", theme_text_color="Secondary", adaptive_height=True))
            row.add_widget(details)
            row.add_widget(MDRaisedButton(text="Review", on_release=lambda _btn, aid=agent_id: self.load_review(aid)))
            card.add_widget(row)
            container.add_widget(card)
        self._set_feedback("Review the submitted details and all three photos before approval.", "info")

    def load_review(self, agent_id: int):
        if self.loading or agent_id <= 0:
            return
        self.loading = True
        self._current_review_agent_id = agent_id
        threading.Thread(target=self._review_worker, args=(agent_id,), daemon=True).start()

    def _review_worker(self, agent_id: int):
        result = self._request("GET", f"/admin/agents/{agent_id}/kyc-review", timeout=(4, 24))
        Clock.schedule_once(lambda _dt, response=result, aid=agent_id: self._apply_review(aid, response))

    def _apply_review(self, agent_id: int, result):
        self.loading = False
        ok, payload = result
        if not ok or not isinstance(payload, dict):
            self._set_feedback(self._extract_detail(payload) or "Unable to open the identity review.", "error")
            return
        self._current_review_agent_id = agent_id
        content = MDBoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(8), padding=dp(8))
        content.bind(minimum_height=content.setter("height"))
        for field, label in (("full_name", "Full name"), ("date_of_birth", "Date of birth"), ("ghana_card_number", "Ghana Card number")):
            content.add_widget(MDLabel(text=f"{label}: {payload.get(field, '')}", adaptive_height=True, text_size=(dp(340), None)))
        content.add_widget(MDLabel(text="Compare the submitted selfie with the Ghana Card photos.", theme_text_color="Secondary", adaptive_height=True))
        for key, label in (("ghana_card_front", "Ghana Card · Front"), ("ghana_card_back", "Ghana Card · Back"), ("selfie_with_id", "Selfie with ID")):
            content.add_widget(MDLabel(text=label, bold=True, adaptive_height=True))
            try:
                encoded = str(payload.get(key) or "").split(",", 1)[1]
                image_bytes = base64.b64decode(encoded, validate=True)
                texture = CoreImage(io.BytesIO(image_bytes), ext="jpg").texture
                image = Image(texture=texture, size_hint_y=None, height=dp(190), allow_stretch=True, keep_ratio=True)
                content.add_widget(image)
            except Exception:
                content.add_widget(MDLabel(text="Photo could not be displayed. Reload the review.", theme_text_color="Error", adaptive_height=True))
        content.add_widget(
            MDRaisedButton(
                text="Approve and activate Agent",
                size_hint_x=1,
                on_release=lambda *_: self.confirm_approval(agent_id),
            )
        )
        show_custom_dialog(self, title=f"Identity review · Agent #{agent_id}", content_cls=content, close_label="Close", auto_dismiss=False)

    def confirm_approval(self, agent_id: int):
        show_confirm_dialog(
            self,
            title="Approve this Agent?",
            message="This grants Agent access and applies the Agent onboarding benefits. Confirm only after reviewing the name, date of birth, card details, and all photos.",
            confirm_label="Approve Agent",
            cancel_label="Review again",
            on_confirm=lambda: self._approve_agent(agent_id),
        )

    def _approve_agent(self, agent_id: int):
        if self.loading:
            return
        self.loading = True
        threading.Thread(target=self._approval_worker, args=(agent_id,), daemon=True).start()

    def _approval_worker(self, agent_id: int):
        result = self._request("PUT", f"/admin/agents/{agent_id}/kyc-approve", timeout=(4, 20))
        Clock.schedule_once(lambda _dt, response=result: self._apply_approval(response))

    def _apply_approval(self, result):
        self.loading = False
        ok, payload = result
        if not ok:
            self._set_feedback(self._extract_detail(payload) or "Agent approval could not be completed.", "error")
            return
        self._set_feedback("Identity approved. Agent access is now active.", "success")
        self.load_pending()
