from types import SimpleNamespace
from unittest.mock import Mock

from features.auth.auth_controller import AuthController


def test_deferred_login_prepares_profile_without_committing_session():
    response = {
        "access_token": "test-token",
        "status": "authenticated",
        "user": {"role": "customer"},
    }
    prepared = {**response, "role": "customer"}
    controller = AuthController(service=SimpleNamespace(login=Mock(return_value=response)))
    controller.prepare_login_result = Mock(return_value=prepared)
    controller.apply_login_result = Mock()

    result = controller.login("0551234567", "1234", defer_apply=True)

    assert result is prepared
    controller.prepare_login_result.assert_called_once_with(response, momo_number="0551234567")
    controller.apply_login_result.assert_not_called()
