from types import SimpleNamespace
from unittest.mock import Mock

from features.auth.auth_controller import AuthController
from api import client as api_client_module


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


def test_login_profile_resolution_uses_auth_me_without_redundant_agent_probe(monkeypatch):
    get = Mock(return_value={
        "status_code": 200,
        "data": {
            "role": "user",
            "is_admin": False,
            "is_agent": False,
        },
    })
    monkeypatch.setattr(api_client_module.api_client, "get", get)
    controller = AuthController(service=SimpleNamespace())

    result = controller.prepare_login_result({"access_token": "token"}, momo_number="0551234567")

    assert result["user"]["role"] == "user"
    assert result["user"]["is_agent"] is False
    get.assert_called_once()
    assert get.call_args.args[0] == "/auth/me"
