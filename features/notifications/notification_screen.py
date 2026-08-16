from __future__ import annotations

from pathlib import Path
from threading import Thread

from kivy.clock import Clock
from kivy.properties import BooleanProperty, ListProperty, StringProperty
from kivy.lang import Builder
from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivymd.uix.snackbar import MDSnackbar, MDSnackbarText

from features.auth.animations import AuthAnimations
from features.notifications.notification_controller import NotificationController
from features.notifications.notification_manager import notification_manager


Builder.load_file(str(Path(__file__).with_name("notification_screen.kv")))


class NotificationScreen(MDScreen):
    loading = BooleanProperty(False)
    notification_rows = ListProperty([])
    unread_count_text = StringProperty("0")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.controller = NotificationController()

    def on_enter(self):
        Clock.schedule_once(self.start_animation, 0.06)
        self.refresh_notifications()

    def start_animation(self, *_args):
        AuthAnimations.enter(self.ids.get("title_block"), 0.00, 0.35)
        AuthAnimations.slide(self.ids.get("list_card"), 0.10, 20, 0.40)

    def refresh_notifications(self):
        if self.loading:
            return
        cached = self.controller.load_cached_notifications()
        if cached:
            self._apply_notifications(cached, source="cache")
        self.loading = True
        self._set_loading(True)
        Thread(target=self._load_notifications_worker, daemon=True).start()

    def _load_notifications_worker(self):
        try:
            items = self.controller.load_notifications()
            Clock.schedule_once(lambda _dt: self._apply_notifications(items, source="network"))
        except Exception:
            Clock.schedule_once(lambda _dt: self._show_cached_fallback())

    def _show_cached_fallback(self):
        cached = self.controller.load_cached_notifications()
        self._apply_notifications(cached, source="cache")
        self.loading = False
        self._set_loading(False)

    def _apply_notifications(self, items, source: str = "network"):
        rows = []
        for item in items or []:
            if not isinstance(item, dict):
                continue
            rows.append(
                {
                    "notification_id": str(item.get("id") or item.get("notification_id") or ""),
                    "title": str(item.get("title") or "Notification"),
                    "message": str(item.get("message") or ""),
                    "date_text": str(item.get("created_at") or item.get("date") or ""),
                    "type": str(item.get("type") or item.get("notification_type") or ""),
                    "is_read": bool(item.get("is_read", False)),
                }
            )
        self.notification_rows = rows
        self.ids.notification_list.data = rows
        notification_manager.update(rows)
        self.unread_count_text = str(notification_manager.unread)
        app = MDApp.get_running_app()
        if app is not None and hasattr(app, "app_state"):
            try:
                app.app_state.set_notifications(rows)
            except Exception:
                pass
        self.loading = False
        self._set_loading(False)

    def mark_read(self, notification_id: str):
        try:
            self.controller.mark_read(notification_id)
            self.refresh_notifications()
        except Exception:
            self.show_message("Unable to mark notification as read.")

    def show_message(self, text: str):
        MDSnackbar(MDSnackbarText(text=str(text or ""))).open()

    def _set_loading(self, active: bool):
        button = self.ids.get("refresh_button")
        if button is not None:
            button.loading = bool(active)
