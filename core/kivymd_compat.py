from __future__ import annotations

from typing import Mapping


_LEGACY_FONT_STYLE_ALIASES = {
    "Title": "H6",
    "Headline": "H5",
    "Body": "Body1",
    "Label": "Caption",
}


def install_kivymd_font_style_compat() -> None:
    """Teach pre-2.0 KivyMD builds about the Material 3 font-style names.

    Desktop currently runs on KivyMD 2.x, where styles such as ``Title`` and
    ``Headline`` are valid. The Android APK build is pinned to KivyMD 1.2.0,
    which still expects legacy names like ``H6`` and ``Body1``. This shim adds
    the newer names as aliases only when an older font-style registry is
    detected.
    """

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


def register_legacy_button_aliases() -> None:
    """Keep older screen imports compatible across KivyMD versions.

    Android is pinned to KivyMD 1.2.0, where the legacy button classes already
    exist. Newer or partial desktop environments may not expose the same names;
    this hook is intentionally best-effort so importing the screens package does
    not fail before the app can install the rest of its compatibility shims.
    """

    try:
        import kivymd.uix.button  # noqa: F401
    except Exception:
        return


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
