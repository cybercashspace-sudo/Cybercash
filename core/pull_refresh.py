from __future__ import annotations

from kivy.clock import Clock
from kivy.factory import Factory
from kivymd.uix.refreshlayout import MDScrollViewRefreshLayout


class PullRefreshScrollView(MDScrollViewRefreshLayout):
    """Native KivyMD pull gesture with one shared callback per screen."""


Factory.register("PullRefreshScrollView", cls=PullRefreshScrollView)


class PullToRefreshMixin:
    """Shared, de-duplicated pull-to-refresh behavior for scrollable screens."""

    _PULL_REFRESH_ROUTES = {
        "home": ("load_dashboard_data", {}),
        "dashboard": ("load_dashboard_data", {}),
        "wallet": ("refresh_wallet", {}),
        "deposit": ("refresh_wallet", {}),
        "withdraw": ("refresh_wallet", {}),
        "transactions": ("load_transactions", {}),
        "bitcoin": ("load_dashboard", {}),
        "notifications": ("refresh_notifications", {}),
        "agent_dashboard": ("load_dashboard", {}),
        "agent_transactions": ("load_transactions", {}),
        "agent_commission": ("load_commission", {}),
        "commission": ("load_commission", {}),
        "loan_screen": ("load_dashboard", {}),
        "loan": ("load_dashboard", {}),
        "repayments": ("load_repayments", {}),
        "repayment": ("load_repayments", {}),
        "profile": ("refresh_profile", {}),
        "settings": ("load_settings", {}),
        "cards": ("refresh_data", {}),
        "virtual_card": ("refresh_data", {}),
        "btc": ("load_btc_data", {"notify": False}),
        "data_bundle": ("load_catalog", {}),
        "escrow": ("load_deals", {"notify_popup": False}),
        "p2p_transfer": ("load_wallet", {"notify": False}),
        "investments": ("load_wallet_balance", {"notify": False}),
        "loans": ("load_policy", {}),
        "agent": ("load_transactions", {}),
        "admin_dashboard": ("load_dashboard", {"silent": True}),
        "admin_agents": ("load_agents", {}),
        "admin_users": ("load_users", {}),
        "admin_transactions": ("load_transactions", {}),
        "admin_withdrawals": ("load_withdrawals", {"silent": True}),
        "admin_revenue": ("load_revenue", {}),
    }

    def __init__(self, **kwargs):
        self._pull_refresh_event = None
        self._pull_refresh_busy = False
        super().__init__(**kwargs)
        self.bind(on_leave=self._hide_pull_refresh_spinners)
        self.bind(on_parent=self._on_pull_refresh_parent)

    def pull_to_refresh(self, *_args):
        if self._pull_refresh_busy:
            return
        self._pull_refresh_busy = True
        try:
            self.refresh_content_from_pull()
        except Exception:
            # Keep gesture handling safe even when an optional screen endpoint fails.
            pass
        self._pull_refresh_event = Clock.schedule_once(self._finish_pull_refresh, 8.0)

    def refresh_content_from_pull(self):
        screen_name = str(getattr(self, "name", "") or "").strip().lower()
        if screen_name == "data":
            if self._screen_refresh_is_busy():
                return
            self._set_wallet_balance()
            network_widget = getattr(self, "ids", {}).get("network")
            network = str(getattr(network_widget, "text", "") or "").strip()
            if network and network.lower() != "unknown":
                self.load_packages(network)
            return
        route = self._PULL_REFRESH_ROUTES.get(screen_name)
        if route:
            method_name, kwargs = route
            method = getattr(self, method_name, None)
            if not callable(method):
                fallback_names = {
                    "transactions": ("refresh_transactions",),
                    "btc": ("load_dashboard",),
                    "virtual_card": ("refresh_data",),
                }.get(screen_name, ())
                method = next(
                    (candidate for name in fallback_names if callable(candidate := getattr(self, name, None))),
                    None,
                )
            if callable(method):
                if self._screen_refresh_is_busy():
                    return
                method(**kwargs)
                if screen_name == "loans":
                    eligibility = getattr(self, "load_eligibility", None)
                    if callable(eligibility):
                        eligibility()
                elif screen_name == "p2p_transfer":
                    fee_status = getattr(self, "load_fee_status", None)
                    if callable(fee_status):
                        fee_status(notify=False)
                elif screen_name == "investments":
                    last_investment = getattr(self, "load_last_active_investment", None)
                    if callable(last_investment):
                        last_investment()
                return

        # Forms keep user-entered values intact. Pulling them never resubmits a payment,
        # resends an OTP, or clears fields; the user can continue with the visible action.
        feedback = getattr(self, "_set_feedback", None)
        if callable(feedback):
            feedback("Your form is up to date. Continue when ready.", "info")
        elif hasattr(self, "feedback_text"):
            try:
                self.feedback_text = "Your form is up to date. Continue when ready."
            except Exception:
                pass

    def _screen_refresh_is_busy(self) -> bool:
        return any(
            bool(getattr(self, attr, False))
            for attr in (
                "loading", "_is_loading", "_loading", "_loading_settings",
                "_busy", "_refreshing", "_refresh_in_progress", "is_loading",
            )
        )

    def _on_pull_refresh_parent(self, _instance, parent):
        if parent is None:
            self._hide_pull_refresh_spinners()

    def _finish_pull_refresh(self, *_args):
        event = self._pull_refresh_event
        self._pull_refresh_event = None
        if event is not None:
            try:
                event.cancel()
            except Exception:
                pass
        self._pull_refresh_busy = False
        self._hide_pull_refresh_spinners()

    def _hide_pull_refresh_spinners(self, *_args):
        walk = getattr(self, "walk", None)
        if callable(walk):
            for widget in walk(restrict=True):
                done = getattr(widget, "refresh_done", None)
                if callable(done):
                    done()
