from pathlib import Path
from threading import Thread

from kivy.clock import Clock
from kivy.lang import Builder
from kivymd.uix.screen import MDScreen
from kivymd.uix.snackbar import MDSnackbar
from kivymd.uix.snackbar import MDSnackbarText

from features.agent.agent_controller import AgentController


Builder.load_file(str(Path(__file__).with_name("agent_kyc.kv")))


class AgentKycScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.controller = AgentController()

    def submit_kyc(self):
        name = self.ids.full_name.text.strip()
        phone = self.ids.phone.text.strip()
        id_number = self.ids.id_number.text.strip()
        document_ref = self.ids.document_ref.text.strip()
        selfie_ref = self.ids.selfie_ref.text.strip()
        Thread(
            target=self._submit_worker,
            args=(name, phone, id_number, document_ref, selfie_ref),
            daemon=True,
        ).start()

    def _submit_worker(self, name, phone, id_number, document_ref, selfie_ref):
        try:
            result = self.controller.submit_kyc(name, phone, id_number, document_ref, selfie_ref)
        except Exception as exc:
            Clock.schedule_once(lambda dt: self.show_message(str(exc) or "Agent KYC submission failed."))
            return

        Clock.schedule_once(lambda dt: self.show_message(self._success_text(result)))

    @staticmethod
    def _success_text(result):
        if isinstance(result, dict):
            reference = result.get("reference") or result.get("transaction_id") or ""
            if reference:
                return f"KYC submitted. Ref: {reference}"
        return "KYC submitted successfully."

    def show_message(self, text):
        MDSnackbar(MDSnackbarText(text=text)).open()

