from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from api.tickets import list_tickets


def test_ticketer_queue_uses_verified_department():
    ticketer = {"oid": "ticketer-1", "role": "Ticketer", "department": "HR Team"}
    db = MagicMock()
    with patch("api.tickets.get_all_tickets", return_value=[]) as get_tickets:
        list_tickets(
            admin_view=True,
            department="IT Team",
            db=db,
            current_user=ticketer,
        )
    get_tickets.assert_called_once_with(
        status=None,
        priority=None,
        search=None,
        requester_id=None,
        department="HR Team",
        assigned_to=None,
        db=db,
    )


def test_ticketer_without_verified_department_is_denied():
    with pytest.raises(HTTPException) as error:
        list_tickets(
            admin_view=True,
            db=MagicMock(),
            current_user={"oid": "ticketer-1", "role": "Ticketer"},
        )
    assert error.value.status_code == 403
