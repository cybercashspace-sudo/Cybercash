from pathlib import Path
from threading import Thread

from kivy.clock import Clock
from kivy.lang import Builder
from kivymd.uix.screen import MDScreen
from core.pull_refresh import PullToRefreshMixin
from components.app_snackbar import show_app_snackbar

from features.agent.agent_controller import AgentController


Builder.load_file(str(Path(__file__).with_name("agent_transactions.kv")))


class AgentTransactionsScreen(PullToRefreshMixin, MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.controller = AgentController()
        self.loading = False

    def on_enter(self):
        self.load_transactions()

    def load_transactions(self):
        if self.loading:
            return
        self.loading = True
        Thread(target=self._load_worker, daemon=True).start()

    def _load_worker(self):
        try:
            rows = self.controller.transaction_history()
        except Exception as exc:
            message = str(exc) or "Unable to load agent transactions."
            Clock.schedule_once(lambda dt, error=message: self._finish_load_error(error))
            return
        Clock.schedule_once(lambda dt: self._apply_transactions_result(rows))

    def _apply_transactions_result(self, rows):
        try:
            self.update_ui(rows)
        except Exception:
            self._finish_load_error("Unable to display agent transactions. Please refresh again.")

    def update_ui(self, rows):
        if "transaction_list" in self.ids:
            self.ids.transaction_list.data = [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []

        self.loading = False
        self._finish_pull_refresh()

    def _finish_load_error(self, message: str) -> None:
        self.loading = False
        self.show_message(message)
        self._finish_pull_refresh()

    def show_message(self, text):
        show_app_snackbar(text)
