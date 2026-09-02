from __future__ import annotations

from kivy.properties import BooleanProperty, NumericProperty, StringProperty
from kivy.metrics import dp
from kivymd.uix.textfield import MDTextField

from theme import GLASS_BORDER, GREEN, PRIMARY, RED, TEXT_PRIMARY, TEXT_SECONDARY


class AppTextField(MDTextField):
    """Shared outlined text field with validation helpers and password toggling."""

    validation_state = StringProperty("default")
    error_message = StringProperty("")
    success_message = StringProperty("")
    password_visible = BooleanProperty(False)
    field_height = NumericProperty(dp(56))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.mode = str(getattr(self, "mode", "") or "rectangle")
        self.helper_text_mode = str(getattr(self, "helper_text_mode", "") or "on_focus")
        self.line_color_normal = list(GLASS_BORDER)
        self.line_color_focus = list(PRIMARY)
        self.helper_text_color_normal = list(TEXT_SECONDARY)
        self.helper_text_color_focus = list(TEXT_PRIMARY)
        self.fill_color = [0, 0, 0, 0]
        self.icon_left_color_normal = list(TEXT_SECONDARY)
        self.icon_left_color_focus = list(PRIMARY)
        self.icon_right_color_normal = list(TEXT_SECONDARY)
        self.icon_right_color_focus = list(PRIMARY)
        self.bind(validation_state=self._apply_validation_state)
        self.bind(field_height=self._apply_height)

    def on_kv_post(self, _base_widget):
        super().on_kv_post(_base_widget)
        self._apply_height()
        try:
            self.padding = [dp(16), dp(12), dp(16), dp(12)]
        except Exception:
            pass
        self._apply_validation_state()

    def _apply_height(self, *_args):
        self.size_hint_y = None
        self.height = float(self.field_height or dp(56))

    def toggle_password_visibility(self):
        if not hasattr(self, "password"):
            return
        self.password_visible = not self.password_visible
        self.password = not self.password_visible
        right_icon = getattr(self, "icon_right", "")
        if right_icon:
            self.icon_right = "eye-off" if self.password_visible else "eye"

    def clear_validation(self):
        self.validation_state = "default"
        self.error_message = ""
        self.success_message = ""
        self.error = False
        self.helper_text = ""
        self.helper_text_mode = "on_focus"

    def set_error(self, message: str):
        self.error_message = str(message or "").strip()
        self.success_message = ""
        self.validation_state = "error"
        self.helper_text = self.error_message
        self.error = True

    def set_success(self, message: str = ""):
        self.success_message = str(message or "").strip()
        self.error_message = ""
        self.validation_state = "success"
        self.helper_text = self.success_message
        self.error = False

    def _apply_validation_state(self, *_args):
        state = str(self.validation_state or "default").strip().lower()
        if state == "error":
            self.line_color_focus = list(RED)
            self.helper_text_color_focus = list(RED)
            self.helper_text_color_normal = list(RED)
            self.helper_text_mode = "on_error"
            self.error = True
            return
        if state == "success":
            self.line_color_focus = list(GREEN)
            self.helper_text_color_focus = list(GREEN)
            self.helper_text_color_normal = list(GREEN)
            self.helper_text_mode = "persistent"
            self.error = False
            return

        self.line_color_focus = list(PRIMARY)
        self.helper_text_color_focus = list(TEXT_SECONDARY)
        self.helper_text_color_normal = list(TEXT_SECONDARY)
        self.helper_text_mode = "on_focus"
        self.error = False


try:
    from kivy.factory import Factory

    Factory.register("AppTextField", cls=AppTextField)
except Exception:
    pass
