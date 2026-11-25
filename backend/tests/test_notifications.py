from backend.core.security import create_access_token
from backend.models import User, UserNotification


def _headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(data={'sub': user.email})}"}


def test_notification_list_is_private_and_mark_read_is_scoped(client, db_session):
    sender = User(email="notice-sender@example.com", password_hash="hashed", is_active=True)
    recipient = User(email="notice-recipient@example.com", password_hash="hashed", is_active=True)
    db_session.add_all([sender, recipient])
    db_session.commit()
    db_session.refresh(sender)
    db_session.refresh(recipient)

    sender_notice = UserNotification(
        user_id=sender.id,
        notification_type="transfer_sent",
        title="Transfer sent",
        message="Your transfer was sent.",
        dedupe_key="test-transfer-sender",
    )
    recipient_notice = UserNotification(
        user_id=recipient.id,
        notification_type="transfer_received",
        title="Transfer received",
        message="You received a transfer.",
        dedupe_key="test-transfer-recipient",
    )
    db_session.add_all([sender_notice, recipient_notice])
    db_session.commit()
    db_session.refresh(sender_notice)
    db_session.refresh(recipient_notice)

    response = client.get("/notifications", headers=_headers(sender))

    assert response.status_code == 200
    assert [item["title"] for item in response.json()["notifications"]] == ["Transfer sent"]
    own_read = client.post(f"/notifications/{sender_notice.id}/read", headers=_headers(sender))
    other_read = client.post(f"/notifications/{recipient_notice.id}/read", headers=_headers(sender))

    assert own_read.status_code == 200
    assert own_read.json()["is_read"] is True
    assert other_read.status_code == 404
