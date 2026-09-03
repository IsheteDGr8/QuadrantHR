from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_employee_request_page_uses_its_page_specific_submit_handler():
    page = (ROOT / "frontend/employee_NM/new-request.html").read_text(encoding="utf-8")

    assert "async function submitEmployeeStandardTicket(event)" in page
    assert (
        'onsubmit="event.preventDefault(); submitEmployeeStandardTicket(event); return false;"'
        in page
    )
    assert 'onclick="event.preventDefault();' not in page


def test_every_standard_ticket_surface_sends_manual_department_as_override():
    pages = (
        ROOT / "frontend/src/views/CreateTicketView.svelte",
        ROOT / "frontend/src/components/CreateTicketModal.svelte",
        ROOT / "frontend/employee_NM/new-request.html",
    )

    for path in pages:
        page = path.read_text(encoding="utf-8")
        assert "department_override" in page

    create_view = pages[0].read_text(encoding="utf-8")
    modal = pages[1].read_text(encoding="utf-8")
    for page in (create_view, modal):
        explicit = page.index("if (departmentSelect !== 'Auto')")
        leave_fallback = page.index("else if (isLeave)", explicit)
        assert explicit < leave_fallback
        assert "AI department routing will be skipped" in page


def test_create_ticket_surfaces_do_not_offer_document_attachments():
    pages = (
        ROOT / "frontend/src/views/CreateTicketView.svelte",
        ROOT / "frontend/src/components/CreateTicketModal.svelte",
        ROOT / "frontend/employee_NM/new-request.html",
        ROOT / "frontend/admin_AV/submit-ticket.html",
    )

    for path in pages:
        page = path.read_text(encoding="utf-8")
        assert 'type="file"' not in page


def test_admin_ticket_detail_only_offers_pdf_export():
    page = (ROOT / "frontend/src/views/TicketDetailView.svelte").read_text(
        encoding="utf-8"
    )

    assert "Export PDF" in page
    assert "Export DOCX" not in page
    assert "apiExportTicketDOCX" not in page


def test_shared_api_client_uses_backend_api_prefix():
    api_client = (ROOT / "frontend/js/api.js").read_text(encoding="utf-8")

    assert 'window.API_BASE_URL || "/api"' in api_client
    assert 'window.API_BASE_URL || "/api/v1"' not in api_client


def test_employee_ticket_pages_load_api_client_before_main_script():
    for relative_path in (
        "frontend/employee_NM/index.html",
        "frontend/employee_NM/my-tickets.html",
        "frontend/employee_NM/new-request.html",
    ):
        page = (ROOT / relative_path).read_text(encoding="utf-8")
        assert "../js/api.js?v=20260816_10" in page
        assert page.index("../js/api.js?v=20260816_10") < page.index(
            "../js/script.js?v=20260816_11"
        )


def test_my_tickets_grid_has_aligned_columns_and_semantic_badges():
    page = (ROOT / "frontend/employee_NM/my-tickets.html").read_text(encoding="utf-8")
    script = (ROOT / "frontend/js/script.js").read_text(encoding="utf-8")

    for heading in ("Request", "Department", "Status", "Priority", "Created", "Action"):
        assert (
            f"<div>{heading}</div>" in page
            or f'<div style="text-align: right;">{heading}</div>' in page
        )
    assert "grid-template-columns: minmax(240px, 2.2fr)" in page
    assert "ticket-badge status-${stClass}" in script
    assert "ticket-badge priority-${prClass}" in script
    assert "ticket-action" in script
    assert ".priority-high { color: #991b1b" in page
    assert "body.dark-mode .priority-high" in page
    assert "body.dark-mode .priority-critical" in page
    assert "body.dark-mode .status-resolved" in page
