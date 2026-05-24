from api import client


class _FakeResponse:
    def __init__(self, status_code: int, payload: object):
        self.status_code = status_code
        self._payload = payload
        self.content = b"{}"

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.urls = []

    def request(self, **kwargs):
        self.urls.append(kwargs["url"])
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def test_normalize_api_url_adds_https_to_bare_domain():
    assert client._normalize_api_url("www.cybercash.space") == "https://www.cybercash.space"


def test_resolve_api_url_normalizes_default_backend(monkeypatch):
    for env_name in ("KIVY_API_URL", "CYBERCASH_API_URL", "BACKEND_URL"):
        monkeypatch.delenv(env_name, raising=False)

    monkeypatch.setattr(client, "_load_app_config", lambda: {})
    monkeypatch.setattr(client, "DEFAULT_API_URL", "www.cybercash.space")

    assert client.resolve_api_url() == "https://www.cybercash.space"


def test_authenticated_request_tries_fallback_after_unauthorized():
    api = client.APIClient(base_url="https://primary.test")
    api.base_urls = ["https://primary.test", "https://fallback.test"]
    api.session = _FakeSession([
        _FakeResponse(401, {"detail": "Could not validate credentials"}),
        _FakeResponse(200, {"first_name": "Ama"}),
    ])

    result = api.get("/auth/me", headers={"Authorization": "Bearer token-from-fallback"})

    assert result["ok"] is True
    assert result["status_code"] == 200
    assert result["data"] == {"first_name": "Ama"}
    assert api.base_url == "https://fallback.test"
    assert api.session.urls == [
        "https://primary.test/auth/me",
        "https://fallback.test/auth/me",
    ]


def test_request_starts_with_last_successful_backend():
    api = client.APIClient(base_url="https://primary.test")
    api.base_urls = ["https://primary.test", "https://fallback.test"]
    api.base_url = "https://fallback.test"
    api.session = _FakeSession([
        _FakeResponse(200, {"status": "ok"}),
    ])

    result = api.get("/health")

    assert result["ok"] is True
    assert api.session.urls == ["https://fallback.test/health"]


def test_authenticated_fallback_rejection_after_timeout_does_not_clear_session():
    api = client.APIClient(base_url="https://primary.test")
    api.base_urls = ["https://primary.test", "https://fallback.test"]
    api.session = _FakeSession([
        client.requests.exceptions.ReadTimeout("primary timed out"),
        _FakeResponse(401, {"detail": "Could not validate credentials"}),
    ])

    result = api.get("/auth/me", headers={"Authorization": "Bearer saved-token"})

    assert result["ok"] is False
    assert result["status_code"] == 0
    assert "connection" in result["data"]["detail"].lower()
    assert api.base_url == "https://primary.test"
    assert api.session.urls == [
        "https://primary.test/auth/me",
        "https://fallback.test/auth/me",
    ]


def test_warmup_only_checks_active_backend():
    api = client.APIClient(base_url="https://primary.test")
    api.base_urls = ["https://primary.test", "https://fallback.test"]
    api.session = _FakeSession([
        client.requests.exceptions.ReadTimeout("primary timed out"),
    ])

    api.warmup()

    assert api.session.urls == ["https://primary.test/health"]


def test_paystack_request_fails_over_after_primary_server_error():
    api = client.APIClient(base_url="https://primary.test")
    api.base_urls = ["https://primary.test", "https://fallback.test"]
    api.session = _FakeSession([
        _FakeResponse(500, {"detail": "Paystack secret key is not configured."}),
        _FakeResponse(200, {"reference": "ok_ref"}),
    ])

    result = api.request(
        "POST",
        "/paystack/initiate",
        payload={"amount": 1.0},
        headers={"Authorization": "Bearer saved-token"},
    )

    assert result["ok"] is True
    assert result["data"] == {"reference": "ok_ref"}
    assert api.base_url == "https://fallback.test"
    assert api.session.urls == [
        "https://primary.test/paystack/initiate",
        "https://fallback.test/paystack/initiate",
    ]
