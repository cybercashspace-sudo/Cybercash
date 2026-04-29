from __future__ import annotations

from kivy.clock import Clock
from kivy.factory import Factory
from kivy.properties import ColorProperty, OptionProperty, StringProperty
import kivymd.uix.button as kivymd_button_module

try:
    from kivymd.uix.button import MDButton, MDButtonIcon, MDButtonText
    _HAS_MODERN_BUTTON_API = True
except ImportError:
    from kivymd.uix.button import (  # type: ignore[attr-defined]
        MDFlatButton as _LegacyFlatButton,
        MDFillRoundFlatIconButton as _LegacyFillRoundFlatIconButton,
        MDRaisedButton as _LegacyRaisedButton,
        MDTextButton as _LegacyTextButtonBuiltin,
    )
    _HAS_MODERN_BUTTON_API = False

if _HAS_MODERN_BUTTON_API:
    class _LegacyTextButton(MDButton):
        text = StringProperty("")
        theme_text_color = OptionProperty("Primary", options=("Primary", "Custom"))
        text_color = ColorProperty([1, 1, 1, 1])

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._text_widget = MDButtonText()
            self.add_widget(self._text_widget)
            self.bind(
                text=self._sync_text_widget,
                theme_text_color=self._sync_text_widget,
                text_color=self._sync_text_widget,
            )
            Clock.schedule_once(self._sync_text_widget, 0)

        def _sync_text_widget(self, *_args):
            self._text_widget.text = str(self.text or "")
            self._text_widget.theme_text_color = self.theme_text_color
            if self.theme_text_color == "Custom":
                self._text_widget.text_color = list(self.text_color)

        def on_md_bg_color(self, _instance, value):
            if value is not None:
                self.theme_bg_color = "Custom"


    class MDRaisedButton(_LegacyTextButton):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.style = "filled"


    class MDFlatButton(_LegacyTextButton):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.style = "text"


    class MDTextButton(_LegacyTextButton):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.style = "text"
            self.theme_bg_color = "Custom"
            self.md_bg_color = [0, 0, 0, 0]


    class MDFillRoundFlatIconButton(MDButton):
        text = StringProperty("")
        icon = StringProperty("")
        theme_text_color = OptionProperty("Primary", options=("Primary", "Custom"))
        text_color = ColorProperty([1, 1, 1, 1])
        theme_icon_color = OptionProperty("Primary", options=("Primary", "Custom"))
        icon_color = ColorProperty([1, 1, 1, 1])

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.style = "filled"
            self.radius = [20]
            self._icon_widget = MDButtonIcon()
            self._text_widget = MDButtonText()
            self.add_widget(self._icon_widget)
            self.add_widget(self._text_widget)
            self.bind(
                text=self._sync_content,
                icon=self._sync_content,
                theme_text_color=self._sync_content,
                text_color=self._sync_content,
                theme_icon_color=self._sync_content,
                icon_color=self._sync_content,
            )
            Clock.schedule_once(self._sync_content, 0)

        def _sync_content(self, *_args):
            self._text_widget.text = str(self.text or "")
            self._text_widget.theme_text_color = self.theme_text_color
            if self.theme_text_color == "Custom":
                self._text_widget.text_color = list(self.text_color)

            self._icon_widget.icon = str(self.icon or "")
            self._icon_widget.theme_icon_color = self.theme_icon_color
            if self.theme_icon_color == "Custom":
                self._icon_widget.icon_color = list(self.icon_color)

        def on_md_bg_color(self, _instance, value):
            if value is not None:
                self.theme_bg_color = "Custom"


    def register_legacy_button_aliases() -> None:
        if "MDRaisedButton" not in Factory.classes:
            Factory.register("MDRaisedButton", cls=MDRaisedButton)
        if "MDFlatButton" not in Factory.classes:
            Factory.register("MDFlatButton", cls=MDFlatButton)
        if "MDTextButton" not in Factory.classes:
            Factory.register("MDTextButton", cls=MDTextButton)
        if "MDFillRoundFlatIconButton" not in Factory.classes:
            Factory.register("MDFillRoundFlatIconButton", cls=MDFillRoundFlatIconButton)

        if not hasattr(kivymd_button_module, "MDRaisedButton"):
            setattr(kivymd_button_module, "MDRaisedButton", MDRaisedButton)
        if not hasattr(kivymd_button_module, "MDFlatButton"):
            setattr(kivymd_button_module, "MDFlatButton", MDFlatButton)
        if not hasattr(kivymd_button_module, "MDTextButton"):
            setattr(kivymd_button_module, "MDTextButton", MDTextButton)
        if not hasattr(kivymd_button_module, "MDFillRoundFlatIconButton"):
            setattr(kivymd_button_module, "MDFillRoundFlatIconButton", MDFillRoundFlatIconButton)
else:
    MDRaisedButton = _LegacyRaisedButton
    MDFlatButton = _LegacyFlatButton
    MDTextButton = _LegacyTextButtonBuiltin
    MDFillRoundFlatIconButton = _LegacyFillRoundFlatIconButton

    def register_legacy_button_aliases() -> None:
        return


register_legacy_button_aliases()
