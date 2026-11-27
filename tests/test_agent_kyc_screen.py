from pathlib import Path

from kivy_app import SCREEN_SPECS


def test_agent_kyc_screen_has_back_button_four_agent_nav_and_document_uploads():
    source = Path("features/agent/agent_kyc.py").read_text(encoding="utf-8")
    layout = Path("features/agent/agent_kyc.kv").read_text(encoding="utf-8")

    assert SCREEN_SPECS["agent_kyc"] == ("features.agent.agent_kyc", "AgentKycScreen")
    assert "class AgentKycScreen(ResponsiveScreen)" in source
    assert 'text: "Back"' in layout
    assert "on_release: root.go_back()" in layout
    assert layout.count("BottomNavBar:") == 1
    assert 'nav_variant: "agent"' in layout
    assert 'active_target: "agent"' in layout
    assert 'root.choose_photo("front")' in layout
    assert 'root.choose_photo("back")' in layout
    assert 'root.choose_photo("selfie")' in layout
    assert 'root.submit_kyc()' in layout


def test_kyc_submission_error_popup_does_not_display_backend_response_text():
    from features.agent.agent_kyc import AgentKycScreen

    messages = []

    class _Harness:
        loading = True
        _show_message = lambda self, title, message: messages.append((title, message))

    harness = _Harness()
    AgentKycScreen._apply_submission(
        harness,
        {"ok": False, "status_code": 500, "data": {"detail": "SQL password leaked"}},
    )

    assert harness.loading is False
    assert len(messages) == 1
    assert messages[0][0] == "Submission not sent"
    assert "SQL password" not in messages[0][1]
    assert "try again" in messages[0][1]


def test_successful_kyc_submission_clears_local_identity_form_and_photo_paths():
    from features.agent.agent_kyc import AgentKycScreen

    class _Field:
        text = "private"

    class _Harness:
        loading = True
        can_submit = True
        kyc_status = "not_submitted"
        status_text = ""
        _photo_paths = {"front": "front.jpg", "back": "back.jpg", "selfie": "selfie.jpg"}
        front_photo_name = back_photo_name = selfie_photo_name = "selected.jpg"
        consent_accepted = True
        ids = {"full_name": _Field(), "date_of_birth": _Field(), "ghana_card_number": _Field()}
        _show_message = lambda self, *_args: None

    harness = _Harness()
    AgentKycScreen._apply_submission(
        harness,
        {"ok": True, "data": {"kyc_status": "pending_admin_review", "notification_sent": True}},
    )

    assert harness.loading is False
    assert harness.can_submit is False
    assert harness.kyc_status == "pending_admin_review"
    assert harness._photo_paths == {"front": "", "back": "", "selfie": ""}
    assert harness.front_photo_name == "No front photo selected"
    assert harness.ids["ghana_card_number"].text == ""
    assert harness.consent_accepted is False
