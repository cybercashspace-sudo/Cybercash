from __future__ import annotations

from features.transactions.transaction_controller import TransactionController
from services.transaction_service import TransactionService


def test_transaction_normalization_exposes_only_safe_detail_fields():
    row = TransactionController.normalize(
        {
            "id": 41,
            "type": "wallet_transfer",
            "amount": "25.50",
            "direction": "debit",
            "currency": "GHS",
            "status": "completed",
            "timestamp": "2026-11-27T12:30:00+00:00",
            "reference": "TX-41",
            "username": "Ama Mensah",
            "momo_number": "0241234567",
            "metadata_json": '{"reference":"hidden-fallback","secret":"must-not-escape"}',
        }
    )

    assert row["transaction_id"] == "41"
    assert row["type"] == "wallet_transfer"
    assert row["amount"] == -25.5
    assert row["status"] == "completed"
    assert row["created_at"] == "2026-11-27T12:30:00+00:00"
    assert row["reference"] == "TX-41"
    assert row["username"] == "Ama Mensah"
    assert row["momo_number"] == "0241234567"
    assert "raw" not in row
    assert "metadata_json" not in row
    assert "secret" not in str(row)


def test_transaction_reference_can_fall_back_to_safe_metadata_key():
    row = TransactionController.normalize(
        {"id": 42, "metadata_json": '{"provider_reference":"PROVIDER-42"}'}
    )

    assert row["reference"] == "PROVIDER-42"


def test_transaction_page_merge_keeps_history_without_duplicate_ids():
    existing = [
        {"transaction_id": "20", "status": "pending"},
        {"transaction_id": "19"},
    ]
    incoming = [
        {"transaction_id": "21"},
        {"transaction_id": "20", "status": "completed"},
    ]

    merged = TransactionController.merge_transactions(existing, incoming)

    assert [row["transaction_id"] for row in merged] == ["21", "20", "19"]
    assert merged[1]["status"] == "completed"


def test_transaction_service_uses_user_scoped_cursor_endpoint(monkeypatch):
    service = TransactionService()
    calls = []

    def get_json(path, *, params):
        calls.append((path, params))
        return {"items": []}

    monkeypatch.setattr(service, "get_json", get_json)
    service.get_transactions(before_id=80, limit=100)
    service.get_transactions(limit=999)

    assert calls == [
        ("/wallet/transactions/me", {"limit": 100, "before_id": 80}),
        ("/wallet/transactions/me", {"limit": 500}),
    ]


def test_transaction_history_does_not_read_shared_unscoped_cache():
    service = TransactionService()

    assert service.load_cached_transactions() == []


def test_transaction_card_dispatches_whitelisted_detail_payload():
    from components.transaction_card import TransactionCard

    received = []
    card = type(
        "CardHarness",
        (),
        {
            "detail_data": {"Reference": "TX-50", "Status": "completed"},
        },
    )()
    card.detail_callback = lambda fields: received.append(fields)

    TransactionCard._dispatch_detail(card)

    assert received == [{"Reference": "TX-50", "Status": "completed"}]


def test_transfer_transaction_details_show_authenticated_sender_and_receiver(monkeypatch):
    from types import SimpleNamespace

    from kivymd.app import MDApp
    from features.transactions.transaction_screen import TransactionScreen

    monkeypatch.setattr(MDApp, "get_running_app", staticmethod(lambda: None))
    monkeypatch.setattr(
        "features.transactions.transaction_screen.session.get_user",
        lambda: {"full_name": "Sender Example", "phone_number": "0242000051"},
    )
    class _Harness:
        _compact_detail = staticmethod(TransactionScreen._compact_detail)
        _format_transaction_time = staticmethod(TransactionScreen._format_transaction_time)

    details = TransactionScreen._transaction_detail_fields(
        _Harness(),
        {
            "type": "TRANSFER",
            "amount": -5,
            "currency": "GHS",
            "direction": "debit",
            "username": "Sender Example",
            "momo_number": "0242000051",
            "counterparty_name": "Receiver Example",
            "reference": "TRX-7",
            "status": "completed",
        },
    )

    assert details["Sender"] == "Sender Example"
    assert details["Receiver"] == "Receiver Example"
    assert details["Reference"] == "TRX-7"
