from __future__ import annotations

from threading import RLock

from core.dashboard_state import DashboardState
from features.home.adapters import TransactionAdapter
from features.home.home_service import HomeService


class HomeController:
    def __init__(self, service: HomeService | None = None):
        self.service = service or HomeService()
        self.state = DashboardState()
        self._lock = RLock()

    def load_cached_dashboard(self) -> dict:
        return self.service.load_cached_dashboard()

    def load_dashboard(self) -> dict:
        return self.service.get_dashboard()

    @staticmethod
    def _as_dict(value) -> dict:
        return dict(value or {}) if isinstance(value, dict) else {}

    @staticmethod
    def _as_list(value) -> list[dict]:
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        return []

    @staticmethod
    def _transaction_key(payload: dict) -> str:
        return str(
            payload.get("id")
            or payload.get("transaction_id")
            or payload.get("reference")
            or payload.get("created_at")
            or payload.get("timestamp")
            or ""
        ).strip()

    @classmethod
    def _extract_wallet(cls, payload) -> dict:
        if isinstance(payload, dict):
            nested = payload.get("wallet")
            if isinstance(nested, dict):
                return dict(nested)
            nested = payload.get("data")
            if isinstance(nested, dict):
                candidate = nested.get("wallet")
                if isinstance(candidate, dict):
                    return dict(candidate)
                if any(key in nested for key in ("balance", "escrow_balance", "loan_balance", "investment_balance")):
                    return dict(nested)
            if any(key in payload for key in ("balance", "escrow_balance", "loan_balance", "investment_balance")):
                return dict(payload)
        return {}

    @classmethod
    def _extract_transaction(cls, payload) -> dict:
        if not isinstance(payload, dict):
            return {}
        for key in ("transaction", "item", "result", "data"):
            nested = payload.get(key)
            if isinstance(nested, dict) and any(k in nested for k in ("amount", "id", "reference", "created_at", "timestamp")):
                return dict(nested)
        if any(k in payload for k in ("amount", "id", "reference", "created_at", "timestamp")):
            return dict(payload)
        return {}

    @classmethod
    def _extract_notification(cls, payload) -> dict:
        if not isinstance(payload, dict):
            return {}
        for key in ("notification", "item", "result", "data"):
            nested = payload.get(key)
            if isinstance(nested, dict) and any(k in nested for k in ("id", "message", "title", "created_at", "timestamp")):
                return dict(nested)
        if any(k in payload for k in ("id", "message", "title", "created_at", "timestamp")):
            return dict(payload)
        return {}

    def _apply_state(
        self,
        payload: dict | None,
        *,
        source: str,
        online: bool,
        loading: bool = False,
        error_text: str = "",
    ) -> dict:
        with self._lock:
            self.state.apply(payload, source=source, online=online, loading=loading)
            snapshot = self.normalize_dashboard(self.state.snapshot())
            snapshot["error_text"] = str(error_text or snapshot.get("error_text") or "")
            return snapshot

    def load_cached_dashboard_state(self) -> dict:
        payload = self.load_cached_dashboard()
        return self._apply_state(payload, source="cache", online=False, loading=False)

    def load_dashboard_state(self) -> dict:
        try:
            payload = self.service.get_dashboard()
            return self._apply_state(payload, source="live", online=True, loading=False)
        except Exception as exc:
            error_text = str(exc or "").strip()
            cached = self.load_cached_dashboard()
            snapshot = self._apply_state(
                cached,
                source="cache",
                online=False,
                loading=False,
                error_text=error_text or "Check connection and try again.",
            )
            if not snapshot.get("error_text"):
                snapshot["error_text"] = "Check connection and try again."
            return snapshot

    def snapshot(self) -> dict:
        with self._lock:
            return self.normalize_dashboard(self.state.snapshot())

    def merge_event_update(self, event_name: str, payload=None) -> dict:
        event = str(event_name or "").strip()
        with self._lock:
            if event == "WalletUpdated":
                wallet = self._extract_wallet(payload)
                if wallet:
                    current = dict(self.state.wallet or {})
                    current.update(wallet)
                    self.state.wallet = current
            elif event == "TransactionCreated":
                transaction = self._extract_transaction(payload)
                if transaction:
                    key = self._transaction_key(transaction)
                    current = [
                        item
                        for item in self.state.transactions or []
                        if self._transaction_key(item) != key
                    ]
                    current.insert(0, transaction)
                    self.state.transactions = current[:20]
            elif event == "NotificationCreated":
                notification = self._extract_notification(payload)
                if notification:
                    notification_key = str(
                        notification.get("id")
                        or notification.get("message")
                        or notification.get("title")
                        or notification.get("created_at")
                        or notification.get("timestamp")
                        or ""
                    ).strip()
                    current = [
                        item
                        for item in self.state.notifications or []
                        if str(
                            item.get("id")
                            or item.get("message")
                            or item.get("title")
                            or item.get("created_at")
                            or item.get("timestamp")
                            or ""
                        ).strip()
                        != notification_key
                    ]
                    current.insert(0, notification)
                    self.state.notifications = current[:20]
            self.state.loading = False
            return self.normalize_dashboard(self.state.snapshot())

    def normalize_dashboard(self, payload: dict | None) -> dict:
        data = dict(payload or {})
        profile = self._as_dict(data.get("profile") or data.get("user"))
        wallet = data.get("wallet") if isinstance(data.get("wallet"), dict) else {}
        transactions = self._as_list(data.get("transactions"))
        notifications = self._as_list(data.get("notifications"))

        wallet_balance = wallet.get("balance")
        if wallet_balance in {None, ""} and "balance" in data:
            wallet_balance = data.get("balance")
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
            "profile": profile,
            "user": dict(profile),
            "wallet": wallet,
            "transactions": transactions,
            "notifications": notifications,
            "source": str(data.get("source") or "live"),
            "online": bool(data.get("online", True)),
            "loading": bool(data.get("loading", False)),
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
