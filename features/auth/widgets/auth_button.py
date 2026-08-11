from __future__ import annotations

from kivy.properties import BooleanProperty, StringProperty

from widgets import GoldButton


class AuthButton(GoldButton):
    loading = BooleanProperty(False)
    busy_text = StringProperty("Loading...")
    normal_text = StringProperty("")

    def on_text(self, *_args):
        if not self.loading:
            self.normal_text = self.text

    def on_loading(self, *_args):
        if self.loading:
            if not self.normal_text:
                self.normal_text = self.text
            self.disabled = True
            self.text = self.busy_text
        else:
            self.disabled = False
            if self.normal_text:
                self.text = self.normal_text
