from pathlib import Path
from threading import Thread

from kivy.clock import Clock
from kivy.lang import Builder
from kivymd.uix.screen import MDScreen
from kivymd.uix.snackbar import MDSnackbar
from kivymd.uix.snackbar import MDSnackbarText

from features.agent.agent_controller import AgentController


Builder.load_file(str(Path(__file__).with_name("commission_screen.kv")))


class CommissionScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.controller = AgentController()

    def on_enter(self):
        self.load_commission()

    def load_commission(self):
        Thread(target=self._load_worker, daemon=True).start()

    def _load_worker(self):
        try:
            data = self.controller.commission_summary()
        except Exception as exc:
            Clock.schedule_once(lambda dt: self.show_message(str(exc) or "Unable to load commissions."))
            return
        Clock.schedule_once(lambda dt: self.update_ui(data))

    def update_ui(self, data):
        if "commission_today" in self.ids:
            self.ids.commission_today.text = data.get("today_text", "GH₵ 0.00")
        if "commission_week" in self.ids:
            self.ids.commission_week.text = data.get("week_text", "GH₵ 0.00")
        if "commission_total" in self.ids:
            self.ids.commission_total.text = data.get("total_text", "GH₵ 0.00")
        if "commission_history" in self.ids:
            self.ids.commission_history.data = data.get("history", [])

    def withdraw_commission(self):
        self.show_message("Commission withdrawal flow will be connected to the backend payout screen.")

    def show_message(self, text):
        MDSnackbar(MDSnackbarText(text=text)).open()

