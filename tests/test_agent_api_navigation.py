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
