from __future__ import annotations

import os
import threading

from kivy.clock import Clock
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import BooleanProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.popup import Popup
from kivy.utils import platform
from kivymd.uix.screen import MDScreen

from api.client import api_client
from core.navigation import navigate_back
from core.popup_manager import show_message_dialog
from core.pull_refresh import PullToRefreshMixin


Builder.load_file(os.path.join(os.path.dirname(__file__), "agent_kyc.kv"))


class AgentKycScreen(PullToRefreshMixin, MDScreen):
    loading = BooleanProperty(False)
    can_submit = BooleanProperty(False)
    status_text = StringProperty("Checking agent registration status…")
    kyc_status = StringProperty("loading")
    front_photo_name = StringProperty("No front photo selected")
    back_photo_name = StringProperty("No back photo selected")
    selfie_photo_name = StringProperty("No selfie photo selected")
    consent_accepted = BooleanProperty(False)

    def __init__(self, **kwargs):
        self._photo_paths = {"front": "", "back": "", "selfie": ""}
        self._file_popup = None
        super().__init__(**kwargs)
        self.bind(on_leave=self._on_leave)

    def on_pre_enter(self, *_args):
        self.load_kyc_status()

    def go_back(self):
        return navigate_back(self)

    def load_kyc_status(self):
        if self.loading:
            return
        self.loading = True
        threading.Thread(target=self._status_worker, daemon=True).start()

    def _status_worker(self):
        result = api_client.request("GET", "/agents/me/kyc", timeout=(4, 12))
        Clock.schedule_once(lambda _dt, response=result: self._apply_status(response))

    def _apply_status(self, response):
        self.loading = False
        if not response.get("ok"):
            self.kyc_status = "unavailable"
            self.can_submit = False
            detail = str((response.get("data") or {}).get("detail") or "")
            if response.get("status_code") == 403:
                self.status_text = "Complete agent registration payment before identity review."
            else:
                self.status_text = "We could not load your verification status. Try again."
            if detail:
                self._show_message("Agent verification", detail)
            return
        payload = response.get("data") or {}
        self.kyc_status = str(payload.get("kyc_status") or "not_submitted")
        self.can_submit = self.kyc_status in {"not_submitted", "rejected", "kyc_failed"}
        labels = {
            "not_submitted": "Registration payment confirmed. Submit your identity details to continue.",
            "pending_admin_review": "Your identity documents are being reviewed by our team.",
            "approved": "Identity approved. Your Agent access is active.",
            "rejected": "Your documents need attention. Review the details and submit again.",
            "kyc_failed": "Your documents need attention. Review the details and submit again.",
        }
        self.status_text = labels.get(self.kyc_status, "Your Agent verification status is being checked.")

    def _is_submit_allowed(self):
        return bool(self.can_submit)

    def choose_photo(self, kind: str):
        if self.loading:
            return
        labels = {"front": "Ghana Card front", "back": "Ghana Card back", "selfie": "Selfie with Ghana Card"}
        if kind not in labels:
            return
        if platform == "android":
            try:
                from android.permissions import request_permissions

                request_permissions(
                    ["android.permission.READ_EXTERNAL_STORAGE", "android.permission.READ_MEDIA_IMAGES"],
                    lambda _permissions, grants, photo_kind=kind: self._on_photo_permission(photo_kind, grants),
                )
                return
            except Exception:
                self._show_message("Photo access unavailable", "Allow photo access in Android settings, then try again.")
                return
        self._open_file_chooser(kind, labels[kind])

    def _on_photo_permission(self, kind, grants):
        if not grants or not any(bool(grant) for grant in grants):
            Clock.schedule_once(lambda _dt: self._show_message("Photo access needed", "Allow photo access to select the required identity photos."))
            return
        Clock.schedule_once(lambda _dt: self._open_file_chooser(kind, {"front": "Ghana Card front", "back": "Ghana Card back", "selfie": "Selfie with Ghana Card"}[kind]))

    def _open_file_chooser(self, kind, label):
        start_path = "/storage/emulated/0" if os.path.isdir("/storage/emulated/0") else os.path.expanduser("~")
        chooser = FileChooserListView(path=start_path, filters=["*.jpg", "*.jpeg", "*.png", "*.webp"])
        body = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(10))
        body.add_widget(chooser)
        actions = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        popup = Popup(title=f"Choose {label}", content=body, size_hint=(0.94, 0.86), auto_dismiss=False)
        actions.add_widget(Button(text="Cancel", on_release=lambda *_: popup.dismiss()))

        def _use_selected(*_args):
            selected = list(getattr(chooser, "selection", []) or [])
            if not selected:
                self._show_message("Choose a photo", "Select a JPG, PNG, or WebP image first.")
                return
            path = os.path.abspath(selected[0])
            if not os.path.isfile(path):
                self._show_message("Photo unavailable", "That file could not be opened. Choose another photo.")
                return
            self._photo_paths[kind] = path
            name = os.path.basename(path)
            setattr(self, f"{kind}_photo_name", name)
            popup.dismiss()

        actions.add_widget(Button(text="Use photo", on_release=_use_selected))
        body.add_widget(actions)
        popup.bind(on_dismiss=lambda *_: self._clear_file_popup(popup))
        self._file_popup = popup
        popup.open()

    def _clear_file_popup(self, popup):
        if self._file_popup is popup:
            self._file_popup = None

    def submit_kyc(self):
        if self.loading:
            return
        if not self._is_submit_allowed():
            self._show_message("Verification unavailable", "Your current verification request cannot be submitted again.")
            return
        full_name = str(self.ids.full_name.text or "").strip()
        dob = str(self.ids.date_of_birth.text or "").strip()
        card_number = str(self.ids.ghana_card_number.text or "").strip().upper()
        if len(full_name) < 2:
            self._show_message("Check your details", "Enter your full legal name as printed on your Ghana Card.")
            return
        if not dob:
            self._show_message("Check your details", "Enter your date of birth in YYYY-MM-DD format.")
            return
        if not card_number:
            self._show_message("Check your details", "Enter your full Ghana Card ID number.")
            return
        if not all(self._photo_paths.values()):
            self._show_message("Photos required", "Add the front, back, and selfie-with-ID photos to continue.")
            return
        if not self.consent_accepted:
            self._show_message("Consent required", "Confirm that these details and photos belong to you.")
            return
        self.loading = True
        fields = {
            "full_name": full_name,
            "date_of_birth": dob,
            "ghana_card_number": card_number,
            "consent": "true",
        }
        paths = dict(self._photo_paths)
        threading.Thread(target=self._submit_worker, args=(fields, paths), daemon=True).start()

    @staticmethod
    def _mime_for_path(path):
        extension = os.path.splitext(path)[1].lower()
        return {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}.get(extension, "application/octet-stream")

    def _submit_worker(self, fields, paths):
        try:
            with open(paths["front"], "rb") as front, open(paths["back"], "rb") as back, open(paths["selfie"], "rb") as selfie:
                files = {
                    "ghana_card_front": (os.path.basename(paths["front"]), front, self._mime_for_path(paths["front"])),
                    "ghana_card_back": (os.path.basename(paths["back"]), back, self._mime_for_path(paths["back"])),
                    "selfie_with_id": (os.path.basename(paths["selfie"]), selfie, self._mime_for_path(paths["selfie"])),
                }
                response = api_client.request_multipart(
                    "POST", "/agents/me/kyc/submit", data=fields, files=files, timeout=(5, 40)
                )
        except Exception:
            response = {"ok": False, "status_code": 0, "data": {"detail": "We could not upload your photos. Check your connection and try again."}}
        Clock.schedule_once(lambda _dt, result=response: self._apply_submission(result))

    def _apply_submission(self, response):
        self.loading = False
        payload = response.get("data") or {}
        if not response.get("ok"):
            detail = str(payload.get("detail") or "Identity submission could not be completed.")
            self._show_message("Submission not sent", detail)
            return
        self.kyc_status = str(payload.get("kyc_status") or "pending_admin_review")
        self.can_submit = False
        self.status_text = "Your identity documents are submitted and awaiting admin approval."
        if payload.get("notification_sent"):
            message = "Your information was encrypted and added to the review queue. The approval team was notified by email; your ID number and photos were not attached."
        else:
            message = "Your information was encrypted and added to the review queue, but the approval email could not be sent. Your application remains available in the Admin Dashboard. Please try again later if the team has not contacted you."
        self._show_message("Identity submitted", message)

    def _show_message(self, title, message):
        show_message_dialog(self, title=title, message=message, close_label="Close")

    def _on_leave(self, *_args):
        popup = self._file_popup
        self._file_popup = None
        if popup is not None:
            popup.dismiss()
