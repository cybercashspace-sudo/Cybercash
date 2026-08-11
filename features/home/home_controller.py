from __future__ import annotations

from features.home.adapters import TransactionAdapter
from features.home.home_service import HomeService


class HomeController:
    def __init__(self, service: HomeService | None = None):
        self.service = service or HomeService()

    def load_cached_dashboard(self) -> dict:
        return self.service.load_cached_dashboard()

    def load_dashboard(self) -> dict:
        return self.service.get_dashboard()

    def normalize_dashboard(self, payload: dict | None) -> dict:
        data = dict(payload or {})
        profile = data.get("profile") if isinstance(data.get("profile"), dict) else {}
        wallet = data.get("wallet") if isinstance(data.get("wallet"), dict) else {}
        transactions = data.get("transactions") if isinstance(data.get("transactions"), list) else []
        notifications = data.get("notifications") if isinstance(data.get("notifications"), list) else []

        wallet_balance = wallet.get("balance")
        try:
            balance_value = float(wallet_balance) if wallet_balance is not None else None
        except Exception:
            balance_value = None

        greeting_name = str(
            profile.get("first_name")
            or profile.get("name")
            or profile.get("full_name")
            or data.get("greeting_name")
            or ""
        ).strip()

        recent_rows = [TransactionAdapter.format(item) for item in transactions[:3]]
        notification_count = len(notifications)

        return {
            "greeting_name": greeting_name,
            "balance": balance_value,
            "recent_rows": recent_rows,
            "error_text": str(data.get("error_text") or ""),
            "is_agent_active": bool(profile.get("is_agent") or profile.get("agent_active")),
            "reset_token": bool(data.get("reset_token", False)),
            "is_verified": bool(profile.get("is_verified") or wallet.get("verified") or wallet.get("status") == "verified"),
            "is_admin": bool(profile.get("is_admin") or str(profile.get("role", "") or "").strip().lower() in {"admin", "super_admin"}),
            "notification_count": notification_count,
        }
