import importlib.util
from pathlib import Path


_STORAGE_PATH = Path(__file__).resolve().parents[1] / "storage.py"
_SPEC = importlib.util.spec_from_file_location("cybercash_test_storage", _STORAGE_PATH)
storage = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(storage)


def test_loan_terms_acceptance_is_versioned_and_scoped_without_plain_identity(monkeypatch):
    payload = {}

    monkeypatch.setattr(storage, "_read_secure_data", lambda: dict(payload))

    def write_secure_data(value):
        payload.clear()
        payload.update(value)

    monkeypatch.setattr(storage, "_write_secure_data", write_secure_data)

    storage.save_loan_terms_acceptance("User-123@example.test", "2026-11-v1")

    assert storage.get_loan_terms_acceptance("user-123@example.test") == "2026-11-v1"
    assert storage.get_loan_terms_acceptance("another-user@example.test") == ""
    assert "user-123@example.test" not in str(payload)
    assert storage.get_loan_terms_acceptance("") == ""


def test_loan_terms_acceptance_requires_both_user_and_version(monkeypatch):
    payload = {}
    monkeypatch.setattr(storage, "_read_secure_data", lambda: dict(payload))
    monkeypatch.setattr(storage, "_write_secure_data", lambda value: payload.update(value))

    storage.save_loan_terms_acceptance("", "2026-11-v1")
    storage.save_loan_terms_acceptance("user-123", "")

    assert payload == {}
