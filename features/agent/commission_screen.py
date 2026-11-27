from pathlib import Path
from threading import Thread

from kivy.clock import Clock
from kivy.lang import Builder
from kivymd.uix.screen import MDScreen
from core.pull_refresh import PullToRefreshMixin
from core.popup_manager import show_backend_result_popup

from features.agent.agent_controller import AgentController


Builder.load_file(str(Path(__file__).with_name("commission_screen.kv")))


class CommissionScreen(PullToRefreshMixin, MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.controller = AgentController()
        self.loading = False

    def on_enter(self):
        self.load_commission()

    def load_commission(self):
        if self.loading:
            return
        self.loading = True
        Thread(target=self._load_worker, daemon=True).start()

    def _load_worker(self):
        try:
            data = self.controller.commission_summary()
        except Exception as exc:
            message = str(exc) or "Unable to load commissions."
            Clock.schedule_once(lambda dt, error=message: self._finish_load_error(error))
            return
        Clock.schedule_once(lambda dt: self._apply_commission_result(data))

    def _apply_commission_result(self, data):
        try:
            self.update_ui(data)
        except Exception:
            self._finish_load_error("Unable to display commissions. Please refresh again.")

    def update_ui(self, data):
        if not isinstance(data, dict):
            self._finish_load_error("Commission data could not be read. Please refresh again.")
            return
        if "commission_today" in self.ids:
            self.ids.commission_today.text = data.get("today_text", "GH₵ 0.00")
        if "commission_week" in self.ids:
            self.ids.commission_week.text = data.get("week_text", "GH₵ 0.00")
        if "commission_total" in self.ids:
            self.ids.commission_total.text = data.get("total_text", "GH₵ 0.00")
        if "commission_history" in self.ids:
            rows = data.get("history", [])
            self.ids.commission_history.data = [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []

        self.loading = False
        self._finish_pull_refresh()

    def _finish_load_error(self, message: str) -> None:
        self.loading = False
        self.show_message(message)
        self._finish_pull_refresh()

    def withdraw_commission(self):
        self.show_message("Commission withdrawal flow will be connected to the backend payout screen.")

    def show_message(self, text):
        show_backend_result_popup(self, text)
