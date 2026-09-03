"""Notification persistence, isolation, and frontend wiring tests."""

import uuid

from fastapi import HTTPException

from api.notifications import NotificationCreateRequest, handle_create_notification
from database.connection import SessionLocal
from database.crud import (
    create_notification,
    get_notifications,
    mark_notification_read,
)
from database.models_db import NotificationDB


def test_notifications_are_database_backed_and_user_scoped():
    user_a = f"notification-user-a-{uuid.uuid4().hex}"
    user_b = f"notification-user-b-{uuid.uuid4().hex}"

    with SessionLocal() as db:
        assert get_notifications([user_a], db=db) == []
        notification = create_notification(
            "Ticket updated", "Your ticket changed.", user_a, db=db
        )

        assert [item["id"] for item in get_notifications([user_a], db=db)] == [
            notification["id"]
        ]
        assert get_notifications([user_b], db=db) == []
        assert not mark_notification_read(notification["id"], [user_b], db=db)
        assert mark_notification_read(notification["id"], [user_a], db=db)
        assert get_notifications([user_a], db=db)[0]["is_read"] is True

        db.query(NotificationDB).filter(
            NotificationDB.id == notification["id"]
        ).delete()
        db.commit()


def test_only_admins_can_create_notifications():
    request = NotificationCreateRequest(
        title="Test", message="Test message", user_id="target-user"
    )
    with SessionLocal() as db:
        try:
            handle_create_notification(
                request,
                current_user={"oid": "employee", "role": "Employee"},
                db=db,
            )
        except HTTPException as error:
            assert error.status_code == 403
        else:
            raise AssertionError("Employee notification creation should be forbidden")


def test_notifications_view_uses_live_api_without_sample_content():
    with open(
        "frontend/src/views/NotificationsView.svelte", encoding="utf-8"
    ) as view_file:
        view = view_file.read()
    with open("frontend/src/lib/api.js", encoding="utf-8") as api_file:
        api = api_file.read()

    assert "apiFetchNotifications" in view
    assert "apiMarkNotificationRead" in view
    assert "onMount(loadNotifications)" in view
    assert "item.is_read" in view
    assert "item.createdAt" in view
    assert "HD-8021" not in view
    assert "Security Advisory" not in view
    assert "apiFetchNotifications" in api
    assert "apiMarkNotificationRead" in api
