from __future__ import annotations

import json

import storage


class _DummyApp:
    def __init__(self, user_data_dir: str):
        self.user_data_dir = user_data_dir


def test_storage_falls_back_to_plain_json_without_cryptography(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "Fernet", None)
    monkeypatch.setattr(storage.App, "get_running_app", lambda: _DummyApp(str(tmp_path)))

    storage.save_token("abc123")
    storage.save_remember_me("0241234567", "Ama")
    storage.save_privacy_mode(False)

    assert storage.get_token() == "abc123"
    assert storage.get_remember_me() == {
        "momo": "0241234567",
        "first_name": "Ama",
    }
    assert storage.get_privacy_mode() is False

    payload = json.loads((tmp_path / "session.json").read_text(encoding="utf-8"))
    assert payload["access_token"] == "abc123"
    assert payload["remember_me"]["momo"] == "0241234567"
    assert payload["privacy_mode"] is False


def test_legacy_remembered_biometric_flag_is_removed(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "Fernet", None)
    monkeypatch.setattr(storage.App, "get_running_app", lambda: _DummyApp(str(tmp_path)))
    storage._write_secure_data(
        {"remember_me": {"momo": "0241234567", "first_name": "Ama", "biometric_enabled": True}}
    )

    assert storage.get_remember_me() == {"momo": "0241234567", "first_name": "Ama"}
    payload = json.loads((tmp_path / "session.json").read_text(encoding="utf-8"))
    assert "biometric_enabled" not in payload["remember_me"]
