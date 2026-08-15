from __future__ import annotations

from importlib import import_module
from typing import Mapping

from kivy.clock import Clock
from kivy.factory import Factory
from kivy.properties import ColorProperty, OptionProperty, StringProperty
import kivymd.uix.button as kivymd_button_module


_LEGACY_FONT_STYLE_ALIASES = {
    "Title": "H6",
    "Headline": "H5",
    "Body": "Body1",
    "Label": "Caption",
}


def install_kivymd_font_style_compat() -> None:
    """Teach pre-2.0 KivyMD builds about the Material 3 font-style names."""

    try:
        from kivymd.font_definitions import theme_font_styles
        from kivymd.uix.label import MDLabel
    except Exception:
        return

    if not isinstance(theme_font_styles, list):
        return

    for alias in _LEGACY_FONT_STYLE_ALIASES:
        if alias not in theme_font_styles:
            theme_font_styles.append(alias)

    try:
        font_style_prop = MDLabel.font_style
        options = list(getattr(font_style_prop, "options", ()) or ())
        changed = False
        for alias in _LEGACY_FONT_STYLE_ALIASES:
            if alias not in options:
                options.append(alias)
                changed = True
        if changed:
            font_style_prop.options = tuple(options)
    except Exception:
        pass


def register_font_style_aliases(theme_font_styles: Mapping | dict) -> None:
    """Mirror Material 3 font-style names into a ThemeManager font map."""

    if not isinstance(theme_font_styles, dict):
        return

    for alias, legacy_name in _LEGACY_FONT_STYLE_ALIASES.items():
        if alias in theme_font_styles or legacy_name not in theme_font_styles:
            continue

        legacy_style = theme_font_styles[legacy_name]
        if isinstance(legacy_style, list):
            theme_font_styles[alias] = list(legacy_style)
        elif isinstance(legacy_style, dict):
            theme_font_styles[alias] = dict(legacy_style)
        else:
            theme_font_styles[alias] = legacy_style


def install_kivymd_text_field_compat() -> None:
    """Bridge text-field mode differences across KivyMD versions."""

    try:
        from kivymd.uix.textfield import MDTextField
    except Exception:
        return

    try:
        mode_prop = MDTextField.mode
        options = list(getattr(mode_prop, "options", ()) or ())
    except Exception:
        return

    has_rectangle = "rectangle" in options
    has_outlined = "outlined" in options

    # Older KivyMD builds already support the legacy rectangle mode used by the app.
    # Only install a compatibility shim when the installed build has moved to outlined-only.
    if has_rectangle or not has_outlined:
        return

    try:
        options.append("rectangle")
        mode_prop.options = tuple(options)
    except Exception:
        return

    if getattr(MDTextField, "_cybercash_text_field_compat", False):
        return

    original_on_mode = getattr(MDTextField, "on_mode", None)

    def on_mode(self, instance, value):
        if value == "rectangle" and has_rectangle:
            return original_on_mode(self, instance, value) if original_on_mode else None
        if value == "rectangle" and has_outlined:
            self.mode = "outlined"
            return None
        if original_on_mode:
            return original_on_mode(self, instance, value)
        return None

    MDTextField.on_mode = on_mode
    MDTextField._cybercash_text_field_compat = True


def install_kivymd_divider_compat() -> None:
    """Expose a stable separator class name across KivyMD versions."""

    try:
        from kivymd.uix.divider import MDDivider
    except Exception:
        try:
            from kivymd.uix.card import MDSeparator as MDDivider
        except Exception:
            return

    try:
        if "MDSeparator" not in Factory.classes:
            Factory.register("MDSeparator", cls=MDDivider)
        if "MDDivider" not in Factory.classes:
            Factory.register("MDDivider", cls=MDDivider)
    except Exception:
        pass


def resolve_kivymd_top_app_bar():
    """Return the top app bar widget class for the installed KivyMD build."""

    candidates = (
        ("kivymd.uix.appbar", "MDTopAppBar"),
        ("kivymd.uix.toolbar.toolbar", "MDTopAppBar"),
        ("kivymd.uix.toolbar.toolbar", "MDToolbar"),
        ("kivymd.uix.toolbar", "MDTopAppBar"),
        ("kivymd.uix.toolbar", "MDToolbar"),
    )

    for module_name, attr_name in candidates:
        try:
            module = import_module(module_name)
            widget = getattr(module, attr_name)
        except Exception:
            continue
        if widget is not None:
            return widget

    raise ImportError("Unable to resolve a KivyMD top app bar widget for this build.")


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
install_kivymd_text_field_compat()
install_kivymd_divider_compat()
