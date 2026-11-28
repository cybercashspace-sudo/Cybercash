from __future__ import annotations

import os
import re
import threading
from io import BytesIO
from datetime import date

from kivy.clock import Clock
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import BooleanProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.popup import Popup
from kivy.utils import platform
from PIL import Image, ImageOps

from api.client import api_client
from core.popup_manager import show_message_dialog
from core.responsive_screen import ResponsiveScreen


Builder.load_file(os.path.join(os.path.dirname(__file__), "agent_kyc.kv"))

MAX_KYC_UPLOAD_BYTES = int(3.5 * 1024 * 1024)
MAX_KYC_IMAGE_PIXELS = 60_000_000


class AgentKycScreen(ResponsiveScreen):
    loading = BooleanProperty(False)
    can_submit = BooleanProperty(False)
    status_text = StringProperty("Checking agent registration status\u2026")
    kyc_status = StringProperty("loading")
    front_photo_name = StringProperty("No front photo selected")
    back_photo_name = StringProperty("No back photo selected")
    selfie_photo_name = StringProperty("No selfie photo selected")
    consent_accepted = BooleanProperty(False)

    def __init__(self, **kwargs):
        self._photo_paths = {"front": "", "back": "", "selfie": ""}
        self._file_popup = None
        self._request_generation = 0
        self._screen_active = False
        super().__init__(**kwargs)
        self.bind(on_leave=self._on_leave)

    def on_pre_enter(self, *_args):
        self._screen_active = True
        self.load_kyc_status()

    def go_back(self):
        return super().go_back()

    def load_kyc_status(self):
        if self.loading:
            return
        self.loading = True
        self._request_generation += 1
        generation = self._request_generation
        self.status_text = "Checking agent registration status…"
        try:
            threading.Thread(target=self._status_worker, args=(generation,), daemon=True).start()
        except Exception:
            self.loading = False
            self.kyc_status = "unavailable"
            self.can_submit = False
            self.status_text = "We could not load your verification status. Try again."
            self._show_message("Agent verification", self.status_text)

    def pull_to_refresh(self):
        self.load_kyc_status()

    def _status_worker(self, generation):
        try:
            result = api_client.request("GET", "/agents/me/kyc", timeout=(4, 12))
        except Exception:
            result = {"ok": False, "status_code": 0, "data": {}}
        Clock.schedule_once(lambda _dt, response=result, gen=generation: self._apply_status(response, gen))

    def _apply_status(self, response, generation=None):
        if generation is not None and generation != getattr(self, "_request_generation", generation):
            return
        self.loading = False
        if not AgentKycScreen._is_screen_active(self):
            return
        if not response.get("ok"):
            self.kyc_status = "unavailable"
            self.can_submit = False
            if response.get("status_code") == 403:
                self.status_text = "Complete agent registration payment before identity review."
                message = self.status_text
            elif response.get("status_code") == 401:
                self.status_text = "Please sign in again to continue identity verification."
                message = self.status_text
            else:
                self.status_text = "We could not load your verification status. Try again."
                message = self.status_text
            self._show_message("Agent verification", message)
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

    def _is_screen_active(self):
        manager = getattr(self, "manager", None)
        if manager is None:
            return bool(getattr(self, "_screen_active", True))
        return getattr(manager, "current_screen", None) is self

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
        if not AgentKycScreen._is_screen_active(self):
            return
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
            setattr(self, f"{kind}_photo_name", "Photo selected")
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
        try:
            birth_date = date.fromisoformat(dob)
        except ValueError:
            self._show_message("Check your details", "Enter your date of birth in YYYY-MM-DD format.")
            return
        if birth_date >= date.today():
            self._show_message("Check your details", "Date of birth must be in the past.")
            return
        if not re.fullmatch(r"GHA-\d{9}-\d", card_number):
            self._show_message("Check your details", "Enter your Ghana Card number like GHA-123456789-0.")
            return
        if not all(self._photo_paths.values()):
            self._show_message("Photos required", "Add the front, back, and selfie-with-ID photos to continue.")
            return
        if not self.consent_accepted:
            self._show_message("Consent required", "Confirm that these details and photos belong to you.")
            return
        self.loading = True
        self._request_generation += 1
        generation = self._request_generation
        fields = {
            "full_name": full_name,
            "date_of_birth": dob,
            "ghana_card_number": card_number,
            "consent": "true",
        }
        paths = dict(self._photo_paths)
        try:
            threading.Thread(target=self._submit_worker, args=(fields, paths, generation), daemon=True).start()
        except Exception:
            self.loading = False
            self._show_message("Submission not sent", "We could not start the secure upload. Please try again.")

    @staticmethod
    def _mime_for_path(path):
        extension = os.path.splitext(path)[1].lower()
        return {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}.get(extension, "application/octet-stream")

    @staticmethod
    def _prepare_upload_photo(path):
        """Orient and compress a selected photo before the bounded upload."""
        try:
            with Image.open(path) as source:
                width, height = source.size
                if width <= 0 or height <= 0 or width * height > MAX_KYC_IMAGE_PIXELS:
                    raise ValueError("This photo is too large to process safely. Choose a lower-resolution image.")
                source.load()
                image = ImageOps.exif_transpose(source).convert("RGB")
        except (OSError, SyntaxError, Image.DecompressionBombError) as exc:
            raise ValueError("Choose a valid JPG, PNG, or WebP image, then try again.") from exc

        for edge in (1800, 1600, 1400, 1200, 1000):
            resized = image.copy()
            resized.thumbnail((edge, edge), Image.Resampling.LANCZOS)
            for quality in (84, 78, 72, 66):
                output = BytesIO()
                resized.save(output, format="JPEG", quality=quality, optimize=True)
                photo = output.getvalue()
                if len(photo) <= MAX_KYC_UPLOAD_BYTES:
                    return photo
        raise ValueError("This photo is still too large after compression. Choose a smaller image.")

    def _submit_worker(self, fields, paths, generation):
        try:
            with BytesIO(self._prepare_upload_photo(paths["front"])) as front, \
                    BytesIO(self._prepare_upload_photo(paths["back"])) as back, \
                    BytesIO(self._prepare_upload_photo(paths["selfie"])) as selfie:
                files = {
                    "ghana_card_front": ("ghana-card-front.jpg", front, "image/jpeg"),
                    "ghana_card_back": ("ghana-card-back.jpg", back, "image/jpeg"),
                    "selfie_with_id": ("selfie-with-id.jpg", selfie, "image/jpeg"),
                }
                response = api_client.request_multipart(
                    "POST", "/agents/me/kyc/submit", data=fields, files=files, timeout=(5, 40), failover=False
                )
        except ValueError as exc:
            response = {
                "ok": False,
                "status_code": 413 if "large" in str(exc).lower() else 400,
                "data": {},
            }
        except Exception:
            response = {"ok": False, "status_code": 0, "data": {"detail": "We could not upload your photos. Check your connection and try again."}}
        Clock.schedule_once(lambda _dt, result=response, gen=generation: self._apply_submission(result, gen))

    def _apply_submission(self, response, generation=None):
        if generation is not None and generation != getattr(self, "_request_generation", generation):
            return
        self.loading = False
        if not AgentKycScreen._is_screen_active(self):
            return
        payload = response.get("data") or {}
        if not response.get("ok"):
            # Keep arbitrary backend response text out of the Kivy UI.
            messages = {
                400: "Check your name, date of birth, ID number, and selected photos, then try again.",
                401: "Please sign in again before submitting your identity documents.",
                403: "Complete agent registration payment before submitting your documents.",
                409: "A verification request is already under review or your Agent account is active.",
                413: "Each photo must be smaller than 4 MB. Choose smaller images and try again.",
                503: "Secure identity storage is temporarily unavailable. Please try again later.",
            }
            message = messages.get(response.get("status_code"), "We could not submit your documents. Check your connection and try again.")
            self._show_message("Submission not sent", message)
            return
        self.kyc_status = str(payload.get("kyc_status") or "pending_admin_review")
        self.can_submit = False
        self.status_text = "Your identity documents are submitted and awaiting admin approval."
        self._photo_paths = {"front": "", "back": "", "selfie": ""}
        self.front_photo_name = "No front photo selected"
        self.back_photo_name = "No back photo selected"
        self.selfie_photo_name = "No selfie photo selected"
        for field_id in ("full_name", "date_of_birth", "ghana_card_number"):
            field = self.ids.get(field_id)
            if field is not None:
                field.text = ""
        self.consent_accepted = False
        if payload.get("notification_sent"):
            message = "Your information was encrypted and added to the review queue. The approval team was notified by email; your ID number and photos were not attached."
        else:
            message = "Your information was encrypted and added to the review queue, but the approval email could not be sent. Your application remains available in the Admin Dashboard. Please try again later if the team has not contacted you."
        self._show_message("Identity submitted", message)

    def _show_message(self, title, message):
        show_message_dialog(self, title=title, message=message, close_label="Close")

    def _on_leave(self, *_args):
        self._screen_active = False
        popup = self._file_popup
        self._file_popup = None
        if popup is not None:
            popup.dismiss()
