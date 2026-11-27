from __future__ import annotations

from kivy.clock import Clock
from kivy.factory import Factory
from kivymd.uix.refreshlayout import MDScrollViewRefreshLayout


class PullRefreshScrollView(MDScrollViewRefreshLayout):
    """Native KivyMD pull gesture with one shared callback per screen."""

    def on_touch_up(self, *args):
        # KivyMD's callback has no completion parameter. Adapt it for our screens
        # while keeping its native overscroll gesture and spinner implementation.
        callback = getattr(self, "refresh_callback", None)
        did_overscroll = bool(getattr(self, "_did_overscroll", False))
        work_spinner = bool(getattr(self, "_work_spinner", False))
        if not did_overscroll or work_spinner or not callable(callback):
            return super().on_touch_up(*args)

        def dispatch_refresh():
            Clock.schedule_once(lambda _dt: callback(self.refresh_done), 0)

        self.refresh_callback = dispatch_refresh
        try:
            return super().on_touch_up(*args)
        finally:
            self.refresh_callback = callback


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
        "agent_commissions": ("load_commission", {}),
        "agent_commission": ("load_commission", {}),
        "commission": ("load_commission", {}),
        "loan_screen": ("refresh_loans", {"silent": False}),
        "loan": ("refresh_loans", {"silent": False}),
        "repayments": ("load_repayments", {}),
        "repayment": ("load_repayments", {}),
        "loan_repayments": ("load_repayments", {}),
        "profile": ("refresh_profile", {}),
        "settings": ("load_settings", {}),
        "agent_kyc": ("load_kyc_status", {}),
        "cards": ("refresh_data", {"notify_popup": True}),
        "virtual_card": ("refresh_data", {"notify_popup": True}),
        "btc": ("load_btc_data", {"notify": False}),
        "data_bundle": ("load_catalog", {}),
        "escrow": ("load_deals", {"notify_popup": True}),
        "p2p_transfer": ("load_wallet", {"notify": False}),
        "investments": ("load_wallet_balance", {"notify": False}),
        "loans": ("refresh_loans", {"silent": False}),
        "agent": ("load_transactions", {}),
        "admin_dashboard": ("load_dashboard", {"silent": True}),
        "admin_agents": ("load_agents", {}),
        "admin_agent_approvals": ("load_pending", {}),
        "admin_users": ("load_users", {}),
        "admin_transactions": ("load_transactions", {}),
        "admin_withdrawals": ("load_withdrawals", {"silent": True}),
        "admin_revenue": ("load_revenue", {}),
    }

    def __init__(self, **kwargs):
        self._pull_refresh_event = None
        self._pull_refresh_busy = False
        self._pull_refresh_done_callback = None
        super().__init__(**kwargs)
        self.bind(on_leave=self._on_pull_refresh_leave)
        self.bind(on_parent=self._on_pull_refresh_parent)

    def on_kv_post(self, base_widget):
        parent = getattr(super(), "on_kv_post", None)
        if callable(parent):
            parent(base_widget)

    def pull_to_refresh(self, done=None, *_args):
        if self._pull_refresh_busy:
            if callable(done):
                done()
            return
        self._pull_refresh_busy = True
        self._pull_refresh_done_callback = done if callable(done) else None
        self._pull_refresh_event = Clock.schedule_once(self._finish_pull_refresh, 8.0)
        try:
            started = self.refresh_content_from_pull()
        except Exception:
            feedback = getattr(self, "_set_feedback", None)
            if callable(feedback):
                feedback("Couldn't refresh right now. Please try again.", "error")
            self._finish_pull_refresh()
            return
        if not started:
            self._finish_pull_refresh()
            return

    def refresh_content_from_pull(self):
        screen_name = str(getattr(self, "name", "") or "").strip().lower()
        if screen_name == "data":
            if self._screen_refresh_is_busy():
                return False
            self._set_wallet_balance()
            network_widget = getattr(self, "ids", {}).get("network")
            network = str(getattr(network_widget, "text", "") or "").strip()
            if network and network.lower() != "unknown":
                self.load_packages(network)
            return True
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
                    return False
                method(**kwargs)
                if screen_name == "p2p_transfer":
                    fee_status = getattr(self, "load_fee_status", None)
                    if callable(fee_status):
                        fee_status(notify=False)
                elif screen_name == "investments":
                    last_investment = getattr(self, "load_last_active_investment", None)
                    if callable(last_investment):
                        last_investment()
                return True

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
        return False

    def _screen_refresh_is_busy(self) -> bool:
        return any(
            bool(getattr(self, attr, False))
            for attr in (
                "screen_loading", "loading", "_is_loading", "_loading", "_loading_settings",
                "_busy", "_refreshing", "_refresh_in_progress", "is_loading",
                "loan_refresh_busy", "loan_submit_busy", "repayment_busy",
                "card_refresh_busy",
                "escrow_busy",
            )
        )

    def _on_pull_refresh_parent(self, _instance, parent):
        if parent is None:
            self._finish_pull_refresh()

    def _on_pull_refresh_leave(self, *_args):
        self._finish_pull_refresh()

    def _finish_pull_refresh(self, *_args):
        event = self._pull_refresh_event
        self._pull_refresh_event = None
        if event is not None:
            try:
                event.cancel()
            except Exception:
                pass
        self._pull_refresh_busy = False
        done = self._pull_refresh_done_callback
        self._pull_refresh_done_callback = None
        done_owner = getattr(done, "__self__", None)
        if callable(done):
            try:
                done()
            except Exception:
                pass
        self._hide_pull_refresh_spinners(skip_widget=done_owner)

    def _hide_pull_refresh_spinners(self, *_args, skip_widget=None):
        walk = getattr(self, "walk", None)
        if callable(walk):
            for widget in walk(restrict=True):
                if widget is skip_widget:
                    continue
                done = getattr(widget, "refresh_done", None)
                if callable(done):
                    done()
