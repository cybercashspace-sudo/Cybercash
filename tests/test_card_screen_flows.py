import inspect

from screens.cards import KV, VirtualCardScreen


def test_virtual_card_request_uses_backend_route_and_confirms_wallet_fee():
    source = inspect.getsource(VirtualCardScreen)

    assert "Request a Virtual Card" in KV
    assert "configured card issuance fee" in source
    assert '"/virtualcards/request"' in source


def test_card_backend_errors_are_safe_for_user_popups():
    safe = VirtualCardScreen._friendly_card_error(
        {"detail": "Traceback: SELECT card_number, cvv FROM virtualcards"},
        "Card update failed. Please try again.",
    )

    assert safe == "Something went wrong on the server. Please try again."
    assert "cvv" not in safe.lower()


def test_card_details_are_hidden_after_screen_exit():
    source = VirtualCardScreen.on_leave.__code__.co_names

    assert "_raw_number" in source
    assert "_raw_cvv" in source
    assert "details_visible" in source


def test_card_backend_result_text_is_not_rendered_below_the_screen():
    assert "root.feedback_text" not in KV


def test_card_screen_keeps_issuance_cvv_once_and_clears_it_when_leaving():
    source = inspect.getsource(VirtualCardScreen)
    assert "_pending_one_time_cvv" in source
    assert "shown once" in source
    assert "self._pending_one_time_cvv = \"\"" in source


def test_virtual_card_response_does_not_expose_stored_cvv_hash():
    from backend.schemas.virtual_card import VirtualCardInDB

    assert "cvv_hashed" not in VirtualCardInDB.model_fields
    assert "cvv" in VirtualCardInDB.model_fields
