from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_login_screen_has_only_required_credentials_and_compact_copy():
    login_kv = _read("screens/login.kv")
    login_py = _read("screens/login.py")

    assert 'text: "Sign in to your account."' in login_kv
    assert 'id: momo_input' in login_kv
    assert 'id: pin_input' in login_kv
    assert 'text: "Forgot PIN?"' in login_kv
    assert 'text: "Create New Account"' in login_kv
    assert "fingerprint" not in login_kv.lower()
    assert "biometric" not in login_py.lower()
    assert 'id: first_name_input' not in login_kv
    assert 'lookup_registered_name' not in login_py
    assert "Use your 10-digit registered Ghana MoMo number" not in login_kv


def test_app_has_no_fingerprint_authentication_path():
    auth_sources = "\n".join(
        _read(path)
        for path in (
            "kivy_app.py",
            "screens/login.py",
            "screens/investments.py",
            "screens/settings.py",
            "buildozer.spec",
        )
    ).lower()

    assert "request_biometric_auth" not in auth_sources
    assert "fingerprint" not in auth_sources
    assert "use_biometric" not in auth_sources


def test_registration_form_keeps_required_details_without_repeated_helper_copy():
    register_kv = _read("screens/register.kv")
    register_py = _read("screens/register.py")

    assert 'id: momo_input' in register_kv
    assert 'id: email_input' in register_kv
    assert 'hint_text: "Email for OTPs and receipts"' in register_kv
    assert 'id: first_name_input' in register_kv
    assert 'id: pin_input' in register_kv
    assert 'text: "Create an account and verify your email."' in register_kv
    assert 'text: "Create your wallet first; agent onboarding opens after verification."' not in register_kv
    assert 'DEFAULT_FEEDBACK_TEXT = ""' in register_py


def test_otp_screen_has_one_short_email_code_prompt():
    otp = _read("screens/otp.py")

    assert 'text: "Enter the code sent to your email."' in otp
    assert 'hint_text: "6-digit OTP"' in otp
    assert 'Enter the 6-digit code sent to your registered email.' not in otp
    assert 'text: "Use the same number linked to your account."' not in otp
    assert 'text: "Back"' in otp
    assert 'on_release: root.go_back()' in otp
    assert 'text: "Back to Login"' not in otp
    assert 'def go_back(self):' in otp


def test_otp_back_returns_to_its_previous_screen(monkeypatch):
    from screens.otp import OTPScreen
    from core import navigation

    calls = []

    class _Manager:
        current = "otp"
        previous_screen = "login"
        _cybercash_screen_history = ["register"]
        _cybercash_nav_busy = False

        @staticmethod
        def has_screen(name):
            return name in {"otp", "login", "register"}

    manager = _Manager()
    monkeypatch.setattr(
        navigation,
        "navigate",
        lambda _manager, target, **kwargs: calls.append((target, kwargs)) or True,
    )
    owner = type("_Harness", (), {"manager": manager, "_active_dialog": None})()

    assert OTPScreen.go_back(owner) is True
    assert calls and calls[0][0] == "register"
    assert calls[0][1]["fallback"] == ""


def test_login_momo_input_normalizes_without_network_lookup(monkeypatch):
    from screens import login

    class _Field:
        text = "+233241234567"

    class _Harness:
        _syncing_momo_input = False
        ids = {"momo_input": _Field()}
        on_momo_input = login.LoginScreen.on_momo_input

    monkeypatch.setattr(login, "normalize_ghana_number", lambda _value: "0241234567")
    screen = _Harness()
    screen.on_momo_input(screen.ids["momo_input"].text)

    assert screen.ids["momo_input"].text == "0241234567"
    assert screen._syncing_momo_input is False
