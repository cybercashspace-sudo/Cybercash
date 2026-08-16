from __future__ import annotations


class RefreshableScreenMixin:
    """Shared refresh-state helpers for screens with inline refresh controls."""

    refresh_button_id = "refresh_button"
    refresh_indicator_id = "refresh_indicator"

    def _get_widget(self, widget_id: str):
        ids = getattr(self, "ids", None)
        if not ids:
            return None
        try:
            return ids.get(widget_id)
        except Exception:
            return None

    def _set_refresh_busy(self, loading: bool) -> None:
        if hasattr(self, "loading"):
            try:
                self.loading = bool(loading)
            except Exception:
                pass

        button = self._get_widget(self.refresh_button_id)
        if button is not None and hasattr(button, "loading"):
            button.loading = bool(loading)

    def _begin_refresh(self, message: str | None = None) -> None:
        self._set_refresh_busy(True)
        indicator = self._get_widget(self.refresh_indicator_id)
        if indicator is not None and hasattr(indicator, "set_loading"):
            indicator.set_loading(message)

    def _complete_refresh(self, message: str | None = None) -> None:
        self._set_refresh_busy(False)
        indicator = self._get_widget(self.refresh_indicator_id)
        if indicator is not None and hasattr(indicator, "finish_refresh"):
            indicator.finish_refresh(message)

    def _fail_refresh(self, message: str | None = None) -> None:
        self._set_refresh_busy(False)
        indicator = self._get_widget(self.refresh_indicator_id)
        if indicator is not None and hasattr(indicator, "fail_refresh"):
            indicator.fail_refresh(message)
