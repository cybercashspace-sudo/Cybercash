from __future__ import annotations

import sys
import types

from core import biometric_auth


class _JavaBase:
    pass


class _CancellationSignal:
    def cancel(self):
        self.cancelled = True


class _FingerprintManager:
    def __init__(self, mode: str):
        self.mode = mode
        self.callback = None

    def isHardwareDetected(self):
        return True

    def hasEnrolledFingerprints(self):
        return True

    def authenticate(self, _crypto, _cancellation, _flags, callback, _handler):
        self.callback = callback
        if self.mode == "raise":
            raise RuntimeError("simulated Android bridge failure")
        callback.onAuthenticationSucceeded(None)
        callback.onAuthenticationSucceeded(None)


class _Activity:
    def __init__(self, manager):
        self.manager = manager
        self.mActivity = self

    def getSystemService(self, _service_name):
        return self.manager

    def runOnUiThread(self, runnable):
        self.runnable = runnable
        runnable.run()


def _install_fake_jnius(monkeypatch, manager):
    activity = _Activity(manager)
    context = type("Context", (), {"FINGERPRINT_SERVICE": "fingerprint"})
    fake_jnius = types.ModuleType("jnius")
    fake_jnius.PythonJavaClass = _JavaBase
    fake_jnius.java_method = lambda _signature: lambda fn: fn
    fake_jnius.autoclass = lambda name: (
        activity
        if name == "org.kivy.android.PythonActivity"
        else context
        if name == "android.content.Context"
        else _CancellationSignal
    )
    fake_jnius.cast = lambda _class_name, value: value
    monkeypatch.setitem(sys.modules, "jnius", fake_jnius)
    monkeypatch.setattr(biometric_auth, "platform", "android")
    return activity


def test_fingerprint_auth_runs_on_ui_thread_and_releases_java_references(monkeypatch):
    manager = _FingerprintManager("success")
    activity = _install_fake_jnius(monkeypatch, manager)
    results = []
    auth = biometric_auth.FingerprintAuthenticator()

    started = auth.authenticate(
        on_success=lambda: results.append("success"),
        on_error=lambda message: results.append(("error", message)),
    )

    assert started is True
    assert activity.runnable is auth._runnable
    assert results == ["success"]
    assert auth._callback is manager.callback

    auth.release()

    assert auth._manager is None
    assert auth._callback is None
    assert auth._runnable is None
    assert auth._cancellation is None


def test_fingerprint_bridge_error_returns_pin_fallback(monkeypatch):
    manager = _FingerprintManager("raise")
    _install_fake_jnius(monkeypatch, manager)
    errors = []
    auth = biometric_auth.FingerprintAuthenticator()

    assert auth.authenticate(
        on_success=lambda: errors.append("unexpected success"),
        on_error=errors.append,
    ) is True

    assert len(errors) == 1
    assert "Sign in with your PIN" in errors[0]


def test_callback_exception_does_not_escape_android_auth_callback(monkeypatch):
    manager = _FingerprintManager("success")
    _install_fake_jnius(monkeypatch, manager)
    auth = biometric_auth.FingerprintAuthenticator()

    def broken_callback():
        raise RuntimeError("simulated UI callback failure")

    assert auth.authenticate(
        on_success=broken_callback,
        on_error=lambda _message: None,
    ) is True


def test_retry_callback_exception_does_not_escape_android_auth_callback(monkeypatch):
    manager = _FingerprintManager("waiting")
    _install_fake_jnius(monkeypatch, manager)
    auth = biometric_auth.FingerprintAuthenticator()

    assert auth.authenticate(
        on_success=lambda: None,
        on_error=lambda _message: None,
        on_failed=lambda: (_ for _ in ()).throw(RuntimeError("simulated UI callback failure")),
    ) is True
    manager.callback.onAuthenticationFailed()
