from __future__ import annotations

from core.dashboard_cache import load_dashboard_cache, save_dashboard_cache


class CacheManager:
    """Thin wrapper around the dashboard cache helpers."""

    def load_dashboard(self) -> dict:
        return load_dashboard_cache()

    def save_dashboard(self, *, profile=None, wallet=None, transactions=None, notifications=None) -> None:
        save_dashboard_cache(
            profile=profile,
            wallet=wallet,
            transactions=transactions,
            notifications=notifications,
        )

