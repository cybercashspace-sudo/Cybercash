from __future__ import annotations

from kivy.properties import BooleanProperty


class RequestGuardMixin:
    loading = BooleanProperty(False)

    def __init__(self, **kwargs):
        self._request_generation = 0
        self._requests_invalidated = False
        super().__init__(**kwargs)

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
        return (
            int(request_id or 0) == int(getattr(self, "_request_generation", 0) or 0)
            and self.parent is not None
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
