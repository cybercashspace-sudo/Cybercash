from types import SimpleNamespace

from core.pull_refresh import PullToRefreshMixin
from screens.loans import KV, LoanScreen


class _Ids(dict):
    __getattr__ = dict.__getitem__


class _PeriodHarness:
    allowed_periods = [1, 7, 14, 30]
    selected_duration = 7
    amount_preview_text = ""
    ids = _Ids(apply_amount=SimpleNamespace(text="100"))
    _set_feedback = lambda *_args, **_kwargs: None
    _show_popup = lambda *_args, **_kwargs: None
    period_available = LoanScreen.period_available
    update_amount_preview = LoanScreen.update_amount_preview
    _parse_float = staticmethod(LoanScreen._parse_float)


def test_loan_period_selection_updates_preview_like_investment():
    screen = _PeriodHarness()

    LoanScreen.set_duration(screen, 30)

    assert screen.selected_duration == 30
    assert "within 30 days" in screen.amount_preview_text
    assert LoanScreen.period_button_bg(screen, 30) == [0.93, 0.77, 0.39, 1]


def test_unsupported_loan_period_does_not_change_selection():
    screen = _PeriodHarness()

    LoanScreen.set_duration(screen, 90)

    assert screen.selected_duration == 7


def test_loans_pull_refresh_uses_async_refresh_route():
    class ScreenHarness:
        name = "loans"
        _PULL_REFRESH_ROUTES = PullToRefreshMixin._PULL_REFRESH_ROUTES
        refresh_count = 0
        eligibility_count = 0

        def _screen_refresh_is_busy(self):
            return False

        def refresh_loans(self, silent=False):
            self.refresh_count += 1
            self.silent = silent
            return True

        def load_eligibility(self):
            self.eligibility_count += 1

    screen = ScreenHarness()

    assert PullToRefreshMixin.refresh_content_from_pull(screen) is True
    assert screen.refresh_count == 1
    assert screen.eligibility_count == 0
    assert screen.silent is False


def test_loan_screen_uses_compact_balance_and_repayment_without_old_cards():
    assert 'text: "Repay Loan"' in KV
    assert 'text: "Summary & Due"' not in KV
    assert 'text: "Eligibility"' not in KV
    assert "root.feedback_text" not in KV


def test_refresh_errors_are_popup_only_and_sanitized():
    class PopupHarness:
        _loan_refresh_show_popup = False
        _loan_refresh_errors = ["fallback message"]
        popup = None

        def _show_popup(self, title, message):
            self.popup = (title, message)

    screen = PopupHarness()
    LoanScreen._finish_loan_refresh_popup(screen)
    assert screen.popup == ("Loan Update", "fallback message")
    assert screen._loan_refresh_show_popup is False

    safe_message = LoanScreen._friendly_loan_error(
        {"detail": "Database error: SELECT secret from users"},
        "Please try again.",
    )
    assert "secret" not in safe_message.lower()
    assert "select" not in safe_message.lower()


def test_loan_popup_is_not_shown_after_leaving_loans():
    class ScreenHarness:
        manager = SimpleNamespace(current="home")
        name = "loans"
        popup_shown = False

    screen = ScreenHarness()
    LoanScreen._show_popup(screen, "Loan Update", "Safe message")
    assert screen.popup_shown is False
