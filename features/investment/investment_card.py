from kivy.properties import BooleanProperty
from kivy.properties import NumericProperty
from kivy.properties import ObjectProperty
from kivy.properties import StringProperty
from kivy.uix.behaviors import ButtonBehavior
from kivymd.uix.card import MDCard


class InvestmentCard(ButtonBehavior, MDCard):
    title = StringProperty("")
    subtitle = StringProperty("")
    detail = StringProperty("")
    status_text = StringProperty("")
    selected = BooleanProperty(False)
    callback = ObjectProperty(None, allownone=True)
    plan_days = NumericProperty(0)

    def on_selected(self, *_):
        if self.selected:
            self.md_bg_color = (0.18, 0.14, 0.02, 1)
            self.line_color = (1, 0.76, 0.12, 1)
        else:
            self.md_bg_color = (0.10, 0.10, 0.10, 1)
            self.line_color = (0.20, 0.20, 0.20, 1)

    def on_release(self):
        if callable(self.callback):
            self.callback(int(self.plan_days or 0))

