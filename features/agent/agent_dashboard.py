from pathlib import Path
from threading import Thread

from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.lang import Builder
from kivy.metrics import dp
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDRaisedButton
from kivymd.uix.label import MDLabel
from kivymd.uix.screen import MDScreen
from kivymd.uix.textfield import MDTextField
from core.pull_refresh import PullToRefreshMixin
from core.popup_manager import show_backend_result_popup, show_confirm_dialog, show_custom_dialog
from core.navigation import navigate

from features.agent.agent_controller import AgentController


Builder.load_file(str(Path(__file__).with_name("agent_dashboard.kv")))


class AgentDashboard(PullToRefreshMixin, MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.controller = AgentController()
        self._agent = {}
        self.loading = False
        self._api_keys_busy = False
        self._api_dialog_open = False
        self._api_dialog_content = None
        self._api_keys_list = None
        self._api_key_name = None
        self._api_key_secret = None
        self._api_key_status = None
        self._api_copy_button = None
        self._api_create_button = None

    def on_enter(self):
        self.load_dashboard()

    def load_dashboard(self):
        if self.loading:
            return
        self.loading = True
        Thread(target=self._load_worker, daemon=True).start()

    def _load_worker(self):
        try:
            data = self.controller.load_dashboard()
        except Exception as exc:
            message = str(exc) or "Unable to load agent dashboard."
            Clock.schedule_once(lambda dt, error=message: self._finish_dashboard_error(error))
            return
        Clock.schedule_once(lambda dt: self._apply_dashboard_result(data))

    def _apply_dashboard_result(self, data):
        try:
            self.update_ui(data)
        except Exception:
            self._finish_dashboard_error("Unable to display agent dashboard. Please refresh again.")

    def update_ui(self, data):
        if not isinstance(data, dict):
            self._finish_dashboard_error("Agent dashboard data could not be read. Please refresh again.")
            return
        self._agent = data.get("agent") or {}
        if not isinstance(self._agent, dict):
            self._agent = {}
        commissions = data.get("commissions") or {}
        if not isinstance(commissions, dict):
            commissions = {}

        if "agent_status" in self.ids:
            self.ids.agent_status.text = self._agent.get("status", "Pending")
        if "commission_balance" in self.ids:
            self.ids.commission_balance.text = self._agent.get("commission_text", "GH₵ 0.00")
        if "today_sales" in self.ids:
            self.ids.today_sales.text = self._agent.get("today_sales_text", "GH₵ 0.00")
        if "customers_served" in self.ids:
            self.ids.customers_served.text = self._agent.get("customers_served_text", "0")
        if "agent_verified" in self.ids:
            self.ids.agent_verified.text = "Verified" if self._agent.get("verified") else "Pending Review"
        if "wallet_balance" in self.ids:
            self.ids.wallet_balance.text = self._agent.get("wallet_balance_text", "GH₵ 0.00")
        if "commission_today" in self.ids:
            self.ids.commission_today.text = commissions.get("today_text", "GH₵ 0.00")
        if "commission_week" in self.ids:
            self.ids.commission_week.text = commissions.get("week_text", "GH₵ 0.00")
        if "commission_total" in self.ids:
            self.ids.commission_total.text = commissions.get("total_text", "GH₵ 0.00")
        if "transaction_list" in self.ids:
            rows = data.get("transactions", [])
            self.ids.transaction_list.data = [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []

        self.loading = False
        self._finish_pull_refresh()

    def _finish_dashboard_error(self, message: str) -> None:
        self.loading = False
        self.show_message(message)
        self._finish_pull_refresh()

    def sell_airtime(self):
        self._go_to_screen("airtime")

    def sell_data(self):
        self._go_to_screen("data_bundle")

    def view_commission(self):
        if self._go_to_screen("agent_commissions"):
            return
        else:
            self.show_message("Commission dashboard is loading.")

    def apply_for_agent(self):
        if self._go_to_screen("agent_kyc"):
            return
        else:
            self.show_message("Agent application is loading.")

    def manage_api_keys(self):
        if self._api_dialog_content is None:
            self._build_api_dialog()
        self._api_dialog_open = True
        show_custom_dialog(
            self,
            title="CyberCash API access",
            content_cls=self._api_dialog_content,
            close_label="Done",
            on_close=self._close_api_dialog,
        )
        self._load_api_keys_async()

    def _build_api_dialog(self):
        content = MDBoxLayout(
            orientation="vertical",
            spacing=dp(8),
            padding=[dp(4), dp(4), dp(4), dp(8)],
            size_hint_y=None,
            adaptive_height=True,
        )
        content.add_widget(MDLabel(
            text=(
                "Create free API access to start a Paystack checkout for customers. "
                "Confirmed payments are credited to your CyberCash wallet. Provider fees may apply. "
                "Keep API secrets private."
            ),
            size_hint_y=None,
            height=dp(78),
            theme_text_color="Secondary",
        ))
        content.add_widget(MDLabel(
            text=(
                "POST /agent-api/v1/payments/checkout · X-CyberCash-API-Key + Idempotency-Key\n"
                'JSON: {"amount": 25, "customer_email": "buyer@example.com"}'
            ),
            size_hint_y=None,
            height=dp(62),
            font_style="Caption",
            theme_text_color="Secondary",
        ))
        self._api_key_name = MDTextField(
            hint_text="Key name (for example, My Store)",
            text="My Store",
            size_hint_y=None,
            height=dp(52),
            max_text_length=60,
        )
        content.add_widget(self._api_key_name)
        self._api_key_status = MDLabel(
            text="Your keys are loading…",
            size_hint_y=None,
            height=dp(42),
            theme_text_color="Secondary",
        )
        content.add_widget(self._api_key_status)
        self._api_key_secret = MDTextField(
            hint_text="New secret appears once",
            readonly=True,
            multiline=False,
            size_hint_y=None,
            height=dp(52),
        )
        content.add_widget(self._api_key_secret)
        actions = MDBoxLayout(orientation="horizontal", spacing=dp(8), size_hint_y=None, height=dp(44))
        self._api_copy_button = MDRaisedButton(
            text="Copy key",
            disabled=True,
            on_release=lambda *_args: self.copy_api_key(),
        )
        self._api_create_button = MDRaisedButton(
            text="Generate key",
            on_release=lambda *_args: self.generate_api_key(),
        )
        actions.add_widget(self._api_copy_button)
        actions.add_widget(self._api_create_button)
        content.add_widget(actions)
        self._api_keys_list = MDBoxLayout(
            orientation="vertical",
            spacing=dp(5),
            size_hint_y=None,
            adaptive_height=True,
        )
        content.add_widget(self._api_keys_list)
        self._api_dialog_content = content

    def _load_api_keys_async(self):
        if self._api_keys_busy:
            return
        self._api_keys_busy = True
        self._api_create_button.disabled = True
        self._start_api_worker("list", None)

    def generate_api_key(self):
        if self._api_keys_busy:
            return
        name = str(getattr(self._api_key_name, "text", "") or "").strip()
        if len(name) < 2:
            show_backend_result_popup(self, "Enter a name with at least 2 characters for this API key.", title="Key name needed")
            return
        self._api_keys_busy = True
        self._api_create_button.disabled = True
        self._api_key_status.text = "Generating a secure key…"
        self._start_api_worker("create", name)

    def revoke_api_key(self, key_id: int):
        if self._api_keys_busy:
            return
        show_confirm_dialog(
            self,
            title="Revoke API key?",
            message="Apps using this key will stop creating new customer checkouts. This cannot be undone.",
            confirm_label="Revoke key",
            on_confirm=lambda: self._revoke_api_key_confirmed(key_id),
        )

    def _revoke_api_key_confirmed(self, key_id: int):
        if self._api_keys_busy:
            return
        self._api_keys_busy = True
        self._api_create_button.disabled = True
        self._start_api_worker("revoke", int(key_id))

    def _start_api_worker(self, action: str, value):
        try:
            Thread(target=self._api_keys_worker, args=(action, value), daemon=True).start()
        except Exception:
            self._api_key_error("API key settings could not be updated. Please try again.")

    def _api_keys_worker(self, action: str, value):
        try:
            if action == "list":
                result = self.controller.api_keys()
            elif action == "create":
                result = self.controller.create_api_key(str(value))
            else:
                result = self.controller.revoke_api_key(int(value))
            Clock.schedule_once(lambda _dt, a=action, data=result: self._apply_api_key_result(a, data))
        except Exception as exc:
            message = str(exc) or "API key settings could not be updated. Please try again."
            Clock.schedule_once(lambda _dt, detail=message: self._api_key_error(detail))

    def _apply_api_key_result(self, action: str, result):
        self._api_keys_busy = False
        self._api_create_button.disabled = False
        payload = result if isinstance(result, dict) else {}
        if action == "create":
            secret = str(payload.get("api_key") or "").strip()
            if not secret:
                self._api_key_error("The API key was not returned. Please try again.")
                return
            if not self._api_dialog_open:
                key_id = payload.get("id")
                if key_id:
                    Thread(target=self._discard_unshown_key, args=(int(key_id),), daemon=True).start()
                return
            self._api_key_secret.text = secret
            self._api_copy_button.disabled = False
            self._api_key_status.text = "Key created. Copy it now; it will not be shown again."
            self._load_api_keys_async()
            return
        if action == "revoke":
            if self._api_dialog_open:
                self._clear_api_secret()
                self._api_key_status.text = str(payload.get("message") or "API key revoked.")
                self._load_api_keys_async()
            else:
                show_backend_result_popup(self, str(payload.get("message") or "API key revoked."), title="API access")
            return
        if not self._api_dialog_open:
            return
        self._render_api_keys(payload)

    def _discard_unshown_key(self, key_id: int):
        try:
            self.controller.revoke_api_key(key_id)
        except Exception:
            pass

    def _render_api_keys(self, payload):
        if self._api_keys_list is None:
            return
        self._api_keys_list.clear_widgets()
        rows = payload.get("items", []) if isinstance(payload, dict) else []
        active_count = 0
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict):
                continue
            revoked = bool(row.get("revoked"))
            if not revoked:
                active_count += 1
            item = MDBoxLayout(orientation="horizontal", spacing=dp(5), size_hint_y=None, height=dp(42))
            item.add_widget(MDLabel(
                text=f"{row.get('name', 'API key')} · {row.get('prefix', '')} · {'Revoked' if revoked else 'Active'}",
                shorten=True,
                theme_text_color="Secondary",
            ))
            if not revoked:
                item.add_widget(MDRaisedButton(
                    text="Revoke",
                    size_hint_x=None,
                    width=dp(82),
                    on_release=lambda _btn, kid=row.get("id"): self.revoke_api_key(int(kid)),
                ))
            self._api_keys_list.add_widget(item)
        if active_count == 0:
            self._api_key_status.text = "No active API keys yet. Create one to get started."
        elif self._api_key_secret.text:
            self._api_key_status.text = "Key created. Copy it now; it will not be shown again."
        else:
            self._api_key_status.text = f"{active_count} active key(s). Secret values cannot be viewed again."

    def _api_key_error(self, message: str):
        self._api_keys_busy = False
        if self._api_create_button is not None:
            self._api_create_button.disabled = False
        if self._api_key_status is not None:
            self._api_key_status.text = "API key request did not complete."
        show_backend_result_popup(self, message, title="API access")

    def copy_api_key(self):
        secret = str(getattr(self._api_key_secret, "text", "") or "").strip()
        if not secret:
            return
        Clipboard.copy(secret)
        self._api_key_status.text = "Key copied. Store it securely; it cannot be viewed again."

    def _clear_api_secret(self):
        if self._api_key_secret is not None:
            self._api_key_secret.text = ""
        if self._api_copy_button is not None:
            self._api_copy_button.disabled = True

    def _close_api_dialog(self):
        self._api_dialog_open = False
        self._clear_api_secret()

    def on_leave(self, *_args):
        self._close_api_dialog()
        parent = getattr(super(), "on_leave", None)
        if callable(parent):
            return parent(*_args)

    def _go_to_screen(self, screen_name: str) -> bool:
        app = MDApp.get_running_app()
        if app is not None and hasattr(app, "go_to_screen"):
            return bool(app.go_to_screen(screen_name, fallback="agent_dashboard", transition_style="fade"))
        if self.manager and self.manager.has_screen(screen_name):
            return bool(navigate(self.manager, screen_name, fallback="agent_dashboard", transition_style="fade"))
        return False

    def _publish_event(self, event_name, payload):
        app = MDApp.get_running_app()
        event_bus = getattr(app, "event_bus", None) if app else None
        publish = getattr(event_bus, "publish", None)
        if callable(publish):
            publish(event_name, payload=payload)

    def show_message(self, text):
        show_backend_result_popup(self, text)
