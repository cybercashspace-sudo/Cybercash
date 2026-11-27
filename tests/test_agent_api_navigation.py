from types import SimpleNamespace


def test_agent_api_tile_opens_the_existing_api_key_manager():
    from screens.agent import AgentScreen, KV

    class _ApiScreen:
        calls = 0

        def manage_api_keys(self):
            self.calls += 1

    api_screen = _ApiScreen()
    screen_manager = SimpleNamespace(
        has_screen=lambda name: name == "agent_dashboard",
        get_screen=lambda _name: api_screen,
    )

    AgentScreen._open_api_manager(SimpleNamespace(root=screen_manager))

    assert api_screen.calls == 1
    assert 'text: "API"' in KV
    assert "root.open_api_access()" in KV
    assert "open_recovery_dialog" not in KV
