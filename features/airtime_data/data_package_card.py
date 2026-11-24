from kivy.properties import BooleanProperty, ObjectProperty, StringProperty

from widgets import GlassCard


class DataPackageCard(GlassCard):
    package_id = StringProperty("")
    title = StringProperty("")
    summary = StringProperty("")
    price_text = StringProperty("")
    selected = BooleanProperty(False)
    callback = ObjectProperty(None, allownone=True)

    def on_selected(self, *_):
        if self.selected:
            self.md_bg_color = (0.18, 0.14, 0.02, 1)
            self.line_color = (1, 0.76, 0.12, 1)
        else:
            self.md_bg_color = (0.10, 0.10, 0.10, 1)
            self.line_color = (0.20, 0.20, 0.20, 1)

    def on_release(self):
        if callable(self.callback):
            self.callback(self.package_id)
