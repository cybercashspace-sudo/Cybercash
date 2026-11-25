from pathlib import Path

from screens.escrow import EscrowScreen, KV


def test_escrow_errors_never_echo_raw_backend_details():
    message = EscrowScreen._friendly_escrow_error(
        "Database error: SELECT password FROM accounts"
    )

    assert message == "We couldn't complete that escrow request. Check your details and try again."
    assert "password" not in message.lower()
    assert "select" not in message.lower()


def test_escrow_screen_uses_compact_copy_and_popup_feedback():
    assert "Escrow overview" not in KV
    assert "Use the verified Ghana MoMo number" not in KV
    assert "root.feedback_text" not in KV
    assert 'nav_variant: "default"' in KV


def test_all_bottom_navigation_variants_use_dashboard_geometry():
    source = Path("core/bottom_nav.py").read_text(encoding="utf-8")

    assert "# Keep the Dashboard's icon-over-label layout consistent on every screen." in source
    assert "is_dashboard = True" in source
