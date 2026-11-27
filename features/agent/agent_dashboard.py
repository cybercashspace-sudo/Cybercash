from pathlib import Path
from threading import Thread

from kivy.clock import Clock
from kivy.lang import Builder
from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from core.pull_refresh import PullToRefreshMixin
from core.popup_manager import show_backend_result_popup
from core.navigation import navigate

from features.agent.agent_controller import AgentController


Builder.load_file(str(Path(__file__).with_name("agent_dashboard.kv")))


class AgentDashboard(PullToRefreshMixin, MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.controller = AgentController()
        self._agent = {}
        self.loading = False

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
