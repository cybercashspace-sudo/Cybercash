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
    assert 'id: first_name_input' not in login_kv
    assert 'lookup_registered_name' not in login_py
    assert "Use your 10-digit registered Ghana MoMo number" not in login_kv


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
