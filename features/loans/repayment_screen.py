from pathlib import Path
from threading import Thread

from kivy.clock import Clock
from kivy.lang import Builder
from kivymd.uix.screen import MDScreen
from core.pull_refresh import PullToRefreshMixin
from core.popup_manager import show_backend_result_popup

from features.loans.loan_controller import LoanController


Builder.load_file(str(Path(__file__).with_name("repayment_screen.kv")))


class RepaymentScreen(PullToRefreshMixin, MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.controller = LoanController()
        self.loading = False

    def on_enter(self):
        self.load_repayments()

    def load_repayments(self):
        if self.loading:
            return
        self.loading = True
        Thread(target=self._load_worker, daemon=True).start()

    def _load_worker(self):
        try:
            data = self.controller.load_dashboard()
        except Exception as exc:
            message = str(exc) or "Unable to load repayments."
            Clock.schedule_once(lambda dt, error=message: self._finish_load_error(error))
            return
        Clock.schedule_once(lambda dt: self._apply_repayment_result(data))

    def _apply_repayment_result(self, data):
        try:
            self.update_ui(data)
        except Exception:
            self._finish_load_error("Unable to display repayments. Please refresh again.")

    def update_ui(self, data):
        if not isinstance(data, dict):
            self._finish_load_error("Repayment data could not be read. Please refresh again.")
            return
        if "repayment_list" in self.ids:
            rows = data.get("repayments", [])
            self.ids.repayment_list.data = [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []
        if "amount_due" in self.ids:
            active = data.get("active_loan") or {}
            if not isinstance(active, dict):
                active = {}
            self.ids.amount_due.text = active.get("title", "GH₵ 0.00")
        if "due_date" in self.ids:
            active = data.get("active_loan") or {}
            if not isinstance(active, dict):
                active = {}
            self.ids.due_date.text = active.get("next_payment_text", "Not available")

        self.loading = False
        self._finish_pull_refresh()

    def _finish_load_error(self, message: str) -> None:
        self.loading = False
        self.show_message(message)
        self._finish_pull_refresh()

    def show_message(self, text):
        show_backend_result_popup(self, text)
