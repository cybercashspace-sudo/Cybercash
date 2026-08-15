from __future__ import annotations

from kivy.metrics import dp
from kivy.properties import BooleanProperty, StringProperty
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.label import MDLabel

from theme import BODY, LABEL, PRIMARY, TEXT_PRIMARY, TEXT_SECONDARY


class SectionHeader(MDBoxLayout):
    """Shared section title/subtitle block."""

    title = StringProperty("")
    subtitle = StringProperty("")
    action_text = StringProperty("")
    show_action = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "horizontal"
        self.size_hint_y = None
        self.padding = [0, 0, 0, 0]
        self.spacing = dp(12)
        self._left = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=dp(2))
        self._title_label = MDLabel(theme_text_color="Custom", text_color=list(TEXT_PRIMARY), font_size=BODY, bold=True, adaptive_height=True)
        self._subtitle_label = MDLabel(theme_text_color="Custom", text_color=list(TEXT_SECONDARY), font_size=LABEL, adaptive_height=True)
        self._action_label = MDLabel(
            theme_text_color="Custom",
            text_color=list(PRIMARY),
            font_size=LABEL,
            halign="right",
            adaptive_height=True,
            size_hint_x=None,
            width=dp(90),
        )
        self._left.add_widget(self._title_label)
        self._left.add_widget(self._subtitle_label)
        self.add_widget(self._left)
        self.add_widget(self._action_label)
        self.bind(title=self._sync, subtitle=self._sync, action_text=self._sync, show_action=self._sync)
        self._sync()

    def _sync(self, *_args):
        self._title_label.text = str(self.title or "")
        self._subtitle_label.text = str(self.subtitle or "")
        self._action_label.text = str(self.action_text or "")
        self._action_label.opacity = 1 if self.show_action and self.action_text else 0
        self._action_label.disabled = not bool(self.show_action and self.action_text)
        self.height = self.minimum_height


