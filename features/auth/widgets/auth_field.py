from __future__ import annotations

from kivy.metrics import dp
from kivy.properties import BooleanProperty
from kivymd.uix.textfield import MDTextField


class AuthField(MDTextField):
    password_visible = BooleanProperty(False)

    def on_kv_post(self, *_args):
        self.size_hint_y = None
        self.height = dp(56)
        if not getattr(self, "helper_text_mode", ""):
            self.helper_text_mode = "on_focus"

    def toggle_password(self) -> None:
        self.password_visible = not self.password_visible
        self.password = not self.password_visible
