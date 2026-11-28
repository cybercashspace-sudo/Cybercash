from types import SimpleNamespace


def test_agent_api_tile_routes_to_the_dedicated_api_screen(monkeypatch):
    from screens.agent import AgentScreen, KV

    calls = []
    app = SimpleNamespace(go_to_screen=lambda *args, **kwargs: calls.append((args, kwargs)) or True)
    monkeypatch.setattr("kivymd.app.MDApp.get_running_app", lambda: app)
    AgentScreen.open_api_access(SimpleNamespace())

    assert calls[0][0][0] == "agent_api"
    assert 'text: "API"' in KV
    assert "root.open_api_access()" in KV
    assert "open_recovery_dialog" not in KV


def test_api_key_generation_stays_on_one_backend_and_surfaces_safe_error():
    from features.agent.agent_api_screen import AgentApiScreen
    from features.agent.agent_service import AgentService

    class _Response:
        data = {"detail": "API access is available after Agent approval."}

        def json(self):
            return self.data

    class _RequestError(Exception):
        response = _Response()

    assert "Agent approval" in AgentApiScreen._friendly_api_error(_RequestError())
    assert AgentApiScreen._friendly_api_error(RuntimeError("Traceback: database password=secret")) != (
        "Traceback: database password=secret"
    )

    calls = []
    service = AgentService()
    service.post_json = lambda *args, **kwargs: calls.append((args, kwargs)) or {"api_key": "once"}
    assert service.create_api_key("My store") == {"api_key": "once"}
    assert calls[0][0] == ("/agents/me/api-keys", {"name": "My store", "mode": "live"})
    assert calls[0][1]["failover"] is False
