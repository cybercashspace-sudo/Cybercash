from pathlib import Path
from threading import Thread

from kivy.clock import Clock
from kivy.lang import Builder
from kivymd.uix.screen import MDScreen
from components.app_snackbar import show_app_snackbar

from features.agent.agent_controller import AgentController


Builder.load_file(str(Path(__file__).with_name("agent_transactions.kv")))


class AgentTransactionsScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.controller = AgentController()

    def on_enter(self):
        self.load_transactions()

    def load_transactions(self):
        Thread(target=self._load_worker, daemon=True).start()

    def _load_worker(self):
        try:
            rows = self.controller.transaction_history()
        except Exception as exc:
            Clock.schedule_once(lambda dt: self.show_message(str(exc) or "Unable to load agent transactions."))
            return
        Clock.schedule_once(lambda dt: self.update_ui(rows))

    def update_ui(self, rows):
        if "transaction_list" in self.ids:
            self.ids.transaction_list.data = rows

    def show_message(self, text):
        show_app_snackbar(text)
