from __future__ import annotations


class ThemeManager:
    DARK_THEME = {
        "mode": "Dark",
        "bg_normal": [0.03, 0.05, 0.08, 1],
        "bg": [0.03, 0.04, 0.06, 1],
        "surface": [0.08, 0.10, 0.13, 0.96],
        "surface_soft": [0.11, 0.14, 0.18, 0.96],
        "glass": [1, 1, 1, 0.05],
        "glass_border": [1, 1, 1, 0.10],
        "overlay": [0.03, 0.03, 0.05, 0.90],
        "gold": [0.95, 0.80, 0.47, 1],
        "emerald": [0.26, 0.78, 0.56, 1],
        "text_primary": [0.96, 0.96, 0.98, 1],
        "text_secondary": [0.74, 0.76, 0.80, 1],
        "dark_bg": [0.05, 0.07, 0.10, 1],
        "card_bg": [0.09, 0.10, 0.12, 0.92],
        "success": [0.60, 0.88, 0.72, 1],
        "error": [0.98, 0.48, 0.41, 1],
        "btc": [0.97, 0.68, 0.15, 1],
    }

    LIGHT_THEME = {
        "mode": "Light",
        "bg_normal": [0.95, 0.97, 0.99, 1],
        "bg": [0.95, 0.97, 0.99, 1],
        "surface": [1, 1, 1, 0.92],
        "surface_soft": [0.92, 0.95, 0.98, 0.96],
        "glass": [1, 1, 1, 0.50],
        "glass_border": [0.10, 0.13, 0.16, 0.10],
        "overlay": [1, 1, 1, 0.38],
        "gold": [0.80, 0.62, 0.12, 1],
        "emerald": [0.06, 0.65, 0.46, 1],
        "text_primary": [0.06, 0.09, 0.12, 1],
        "text_secondary": [0.38, 0.42, 0.48, 1],
        "dark_bg": [0.92, 0.95, 0.98, 1],
        "card_bg": [1, 1, 1, 0.92],
        "success": [0.20, 0.62, 0.42, 1],
        "error": [0.92, 0.34, 0.27, 1],
        "btc": [0.87, 0.56, 0.12, 1],
    }

    def __init__(self, app):
        self.app = app
        self.current = "Dark"

    def apply(self, mode: str = "Dark", *, animate: bool = False) -> None:
        normalized = "Light" if str(mode or "").strip().lower() == "light" else "Dark"
        palette = self.LIGHT_THEME if normalized == "Light" else self.DARK_THEME
        self.current = normalized
        self._apply_palette(palette)

    def toggle(self, *, animate: bool = False) -> None:
        self.apply("Light" if self.current == "Dark" else "Dark", animate=animate)

    def _apply_palette(self, palette: dict) -> None:
        app = self.app
        if app is None:
            return

        if hasattr(app, "theme_mode"):
            app.theme_mode = str(palette.get("mode", "Dark"))

        theme_cls = getattr(app, "theme_cls", None)
        if theme_cls is not None:
            try:
                theme_cls.theme_style = str(palette.get("mode", "Dark"))
            except Exception:
                pass
            try:
                theme_cls.bg_normal = list(palette.get("bg_normal", palette.get("bg", [0.03, 0.05, 0.08, 1])))
            except Exception:
                pass
            try:
                theme_cls.bg_dark = list(palette.get("bg", [0.03, 0.04, 0.06, 1]))
            except Exception:
                pass

        app.apply_theme_palette(palette)
