from __future__ import annotations

import os

import start_kivy


def test_configure_runtime_preserves_explicit_api_url(monkeypatch, tmp_path):
    monkeypatch.setattr(start_kivy, "ROOT", tmp_path)
    monkeypatch.setattr(start_kivy, "PYTHON311", tmp_path / "Python311")
    monkeypatch.delenv("KIVY_API_URL", raising=False)
    monkeypatch.delenv("CYBERCASH_API_URL", raising=False)
    monkeypatch.delenv("BACKEND_URL", raising=False)
    monkeypatch.delenv("KIVY_HOME", raising=False)
    monkeypatch.setenv("CYBERCASH_API_URL", "https://www.cybercash.space")

    start_kivy.configure_runtime()

    assert os.environ["CYBERCASH_API_URL"] == "https://www.cybercash.space"
    assert "KIVY_API_URL" not in os.environ
    assert os.environ["KIVY_HOME"] == str(tmp_path / ".kivy_runtime")
