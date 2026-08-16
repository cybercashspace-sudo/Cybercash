from pathlib import Path
from threading import Thread

from kivy.clock import Clock
from kivy.lang import Builder
from kivymd.uix.screen import MDScreen
from components.app_snackbar import show_app_snackbar

from features.loans.loan_controller import LoanController


Builder.load_file(str(Path(__file__).with_name("repayment_screen.kv")))


class RepaymentScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.controller = LoanController()

    def on_enter(self):
        self.load_repayments()

    def load_repayments(self):
        Thread(target=self._load_worker, daemon=True).start()

    def _load_worker(self):
        try:
            data = self.controller.load_dashboard()
        except Exception as exc:
            Clock.schedule_once(lambda dt: self.show_message(str(exc) or "Unable to load repayments."))
            return
        Clock.schedule_once(lambda dt: self.update_ui(data))

    def update_ui(self, data):
        if "repayment_list" in self.ids:
            self.ids.repayment_list.data = data.get("repayments", [])
        if "amount_due" in self.ids:
            active = data.get("active_loan") or {}
            self.ids.amount_due.text = active.get("title", "GH₵ 0.00")
        if "due_date" in self.ids:
            active = data.get("active_loan") or {}
            self.ids.due_date.text = active.get("next_payment_text", "Not available")

    def show_message(self, text):
        show_app_snackbar(text)
