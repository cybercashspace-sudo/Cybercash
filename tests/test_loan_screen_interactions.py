from types import SimpleNamespace

from core.pull_refresh import PullToRefreshMixin
from screens.loans import LoanScreen


class _Ids(dict):
    __getattr__ = dict.__getitem__


class _PeriodHarness:
    allowed_periods = [1, 7, 14, 30]
    selected_duration = 7
    amount_preview_text = ""
    ids = _Ids(apply_amount=SimpleNamespace(text="100"))
    _set_feedback = lambda *_args, **_kwargs: None
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

        def _screen_refresh_is_busy(self):
            return False

        def refresh_loans(self):
            self.called = True
            return True

    screen = ScreenHarness()

    assert PullToRefreshMixin.refresh_content_from_pull(screen) is True
    assert screen.called is True
