from api import client


def test_normalize_api_url_adds_https_to_bare_domain():
    assert client._normalize_api_url("www.cybercash.space") == "https://www.cybercash.space"


def test_resolve_api_url_normalizes_default_backend(monkeypatch):
    for env_name in ("KIVY_API_URL", "CYBERCASH_API_URL", "BACKEND_URL"):
        monkeypatch.delenv(env_name, raising=False)

    monkeypatch.setattr(client, "_load_app_config", lambda: {})
    monkeypatch.setattr(client, "DEFAULT_API_URL", "www.cybercash.space")

    assert client.resolve_api_url() == "https://www.cybercash.space"
