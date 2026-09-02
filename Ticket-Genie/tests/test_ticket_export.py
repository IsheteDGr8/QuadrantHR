"""Ticket PDF export behavior, authorization, and frontend wiring."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from services.document_service import generate_ticket_docx, generate_ticket_pdf

ROOT = Path(__file__).resolve().parents[1]
API_JS = (ROOT / "frontend" / "js" / "api.js").read_text(encoding="utf-8")
EMPLOYEE_JS = (ROOT / "frontend" / "employee_NM" / "employee.js").read_text(
    encoding="utf-8"
)
DETAIL_HTML = (ROOT / "frontend" / "employee_NM" / "ticket-detail.html").read_text(
    encoding="utf-8"
)

TICKET = {
    "id": "HD-9001",
    "title": "Benefits question",
    "department": "HR Team",
    "category": "Benefits",
    "priority": "High",
    "status": "Open",
    "createdAt": "2026-08-18T10:00:00",
    "requester_id": "employee-oid",
    "description": "I need help understanding my benefits.",
}
COMMENTS = [
    {
        "createdAt": "2026-08-18T10:05:00",
        "sender_role": "Employee",
        "message": "Can HR help?",
    },
    {
        "createdAt": "2026-08-18T10:10:00",
        "sender_role": "HR Support",
        "message": "Yes, we can help.",
    },
]


def test_pdf_generation_accepts_complete_ticket_and_chat_history():
    pdf = generate_ticket_pdf("HD-9001", ticket=TICKET, comments=COMMENTS)
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1000


def test_document_text_export_contains_relevant_fields_and_chat():
    document = generate_ticket_docx(
        "HD-9001", ticket=TICKET, comments=COMMENTS
    ).decode()
    for expected in (
        "HD-9001",
        "Benefits question",
        "HR Team",
        "High",
        "I need help understanding my benefits.",
        "Employee: Can HR help?",
        "HR Support: Yes, we can help.",
    ):
        assert expected in document


def test_employee_export_excludes_private_notes_and_uses_supplied_record():
    from api.tickets import export_ticket_document

    comments = COMMENTS + [{"sender_role": "Private", "message": "Internal only"}]
    with (
        patch("api.tickets.get_ticket_by_id", return_value=TICKET),
        patch("database.crud.get_ticket_comments", return_value=comments),
        patch(
            "services.document_service.generate_ticket_pdf", return_value=b"%PDF-test"
        ) as generate,
    ):
        response = export_ticket_document(
            "HD-9001",
            format="pdf",
            db=MagicMock(),
            current_user={
                "oid": "employee-oid",
                "email": "employee@example.com",
                "role": "Employee",
            },
        )

    assert response.body == b"%PDF-test"
    passed_comments = generate.call_args.kwargs["comments"]
    assert [comment["sender_role"] for comment in passed_comments] == [
        "Employee",
        "HR Support",
    ]


def test_employee_cannot_export_someone_elses_ticket():
    from api.tickets import export_ticket_document

    with patch("api.tickets.get_ticket_by_id", return_value=TICKET):
        with pytest.raises(HTTPException) as exc:
            export_ticket_document(
                "HD-9001",
                db=MagicMock(),
                current_user={"oid": "different-employee", "role": "Employee"},
            )
    assert exc.value.status_code == 403


def test_employee_export_uses_authenticated_blob_download():
    assert "async function apiDownloadTicketDocument" in API_JS
    assert "await res.blob()" in API_JS
    assert "URL.createObjectURL(blob)" in API_JS
    assert "downloadTicketDocument" in EMPLOYEE_JS
    assert "getExportUrl(ticket.id" not in EMPLOYEE_JS
    assert "../js/api.js?v=20260818_3" in DETAIL_HTML
    assert "employee.js?v=20260818_3" in DETAIL_HTML
