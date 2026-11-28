from __future__ import annotations

from kivy.properties import BooleanProperty


class RequestGuardMixin:
    loading = BooleanProperty(False)

    def __init__(self, **kwargs):
        self._request_generation = 0
        self._requests_invalidated = False
        super().__init__(**kwargs)

    def on_kv_post(self, base_widget):
        # ResponsiveScreen already tracks the loading property and request count.
        # Do not install the removed full-screen request overlay here.
        parent = getattr(super(), "on_kv_post", None)
        if callable(parent):
            parent(base_widget)

    def _next_request_generation(self) -> int:
        self._request_generation += 1
        self._requests_invalidated = False
        return self._request_generation

    def _invalidate_pending_requests(self) -> None:
        if getattr(self, "_requests_invalidated", False):
            return
        self._request_generation += 1
        self._requests_invalidated = True
        self._set_loading(False)

    def _is_current_request(self, request_id: int) -> bool:
        manager = getattr(self, "manager", None)
        current_screen = getattr(manager, "current_screen", None) if manager is not None else None
        return (
            int(request_id or 0) == int(getattr(self, "_request_generation", 0) or 0)
            and self.parent is not None
            and current_screen is self
            and not getattr(self, "_requests_invalidated", False)
        )

    def on_pre_leave(self, *_args):
        self._invalidate_pending_requests()
        parent_on_pre_leave = getattr(super(), "on_pre_leave", None)
        if callable(parent_on_pre_leave):
            return parent_on_pre_leave(*_args)

    def on_leave(self, *_args):
        self._invalidate_pending_requests()
        parent_on_leave = getattr(super(), "on_leave", None)
        if callable(parent_on_leave):
            return parent_on_leave(*_args)
