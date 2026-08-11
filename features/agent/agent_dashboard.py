from pathlib import Path
from threading import Thread

from kivy.clock import Clock
from kivy.lang import Builder
from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivymd.uix.snackbar import MDSnackbar
from kivymd.uix.snackbar import MDSnackbarText

from features.agent.agent_controller import AgentController


Builder.load_file(str(Path(__file__).with_name("agent_dashboard.kv")))


class AgentDashboard(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.controller = AgentController()
        self._agent = {}

    def on_enter(self):
        self.load_dashboard()

    def load_dashboard(self):
        Thread(target=self._load_worker, daemon=True).start()

    def _load_worker(self):
        try:
            data = self.controller.load_dashboard()
        except Exception as exc:
            Clock.schedule_once(lambda dt: self.show_message(str(exc) or "Unable to load agent dashboard."))
            return
        Clock.schedule_once(lambda dt: self.update_ui(data))

    def update_ui(self, data):
        self._agent = data.get("agent") or {}
        commissions = data.get("commissions") or {}

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
            self.ids.transaction_list.data = data.get("transactions", [])

    def sell_airtime(self):
        if self.manager:
            self.manager.current = "airtime"

    def sell_data(self):
        if self.manager:
            self.manager.current = "data_bundle"

    def view_commission(self):
        if self.manager and "agent_commissions" in self.manager.screen_names:
            self.manager.current = "agent_commissions"
        else:
            self.show_message("Commission dashboard is loading.")

    def apply_for_agent(self):
        if self.manager and "agent_kyc" in self.manager.screen_names:
            self.manager.current = "agent_kyc"
        else:
            self.show_message("Agent application is loading.")

    def _publish_event(self, event_name, payload):
        app = MDApp.get_running_app()
        event_bus = getattr(app, "event_bus", None) if app else None
        publish = getattr(event_bus, "publish", None)
        if callable(publish):
            publish(event_name, payload=payload)

    def show_message(self, text):
        MDSnackbar(MDSnackbarText(text=text)).open()

