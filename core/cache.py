from __future__ import annotations

from core.config import config as app_config
from core.dashboard_cache import load_dashboard_cache, save_dashboard_cache


class CacheManager:
    """Thin wrapper around the dashboard cache helpers."""

    def __init__(self, ttl_seconds: int | None = None):
        self.ttl_seconds = int(ttl_seconds if ttl_seconds is not None else app_config.cache_ttl)

    def load_dashboard(self) -> dict:
        return load_dashboard_cache()

    def load_snapshot(self) -> dict:
        return self.load_dashboard()

    def save_dashboard(self, *, profile=None, wallet=None, transactions=None, notifications=None) -> None:
        save_dashboard_cache(
            profile=profile,
            wallet=wallet,
            transactions=transactions,
            notifications=notifications,
        )

    def clear_dashboard(self) -> None:
        save_dashboard_cache(profile={}, wallet={}, transactions=[], notifications=[])
