"""Regression checks for authenticated department-admin ticket loading."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_JS = (ROOT / "frontend" / "js" / "api.js").read_text(encoding="utf-8")
AUTH_JS = (ROOT / "frontend" / "js" / "azure-auth.js").read_text(encoding="utf-8")
ADMIN_DIR = ROOT / "frontend" / "admin_AV"


def test_ticket_fetch_waits_for_authentication_restoration():
    ticket_fetch = API_JS[
        API_JS.index("async function apiFetchTickets") : API_JS.index(
            "async function apiFetchTicket(ticketId)"
        )
    ]
    assert "window.AzureAuth?.ready" in ticket_fetch
    assert "await window.AzureAuth.ready" in ticket_fetch
    assert ticket_fetch.index("await window.AzureAuth.ready") < ticket_fetch.index(
        "fetch(`${API_BASE_URL}/tickets"
    )


def test_azure_auth_exposes_ready_promise_after_session_check():
    assert "const authReady = new Promise" in AUTH_JS
    assert "ready: authReady" in AUTH_JS
    assert "user = await autoLoginAzure()" in AUTH_JS
    assert "resolveAuthReady(user)" in AUTH_JS


def test_admin_ticket_views_explicitly_request_admin_scope():
    ticket_views = (
        "admin.js",
        "admin_dashboard.html",
        "analytics.html",
        "archive.html",
        "inbox.html",
        "ticket_archive.html",
    )
    for name in ticket_views:
        source = (ADMIN_DIR / name).read_text(encoding="utf-8")
        assert "fetchFn({ adminView: true })" in source, name


def test_frontend_does_not_supply_an_hr_identity_or_department_override():
    # The authenticated backend mapping remains the source of department
    # scope; the client only requests admin mode.
    inbox = (ADMIN_DIR / "inbox.html").read_text(encoding="utf-8")
    assert "requesterId" not in inbox
    assert 'department: "HR Team"' not in inbox


def test_primary_admin_ticket_pages_load_matching_auth_and_api_versions():
    dashboard = (ADMIN_DIR / "admin_dashboard.html").read_text(encoding="utf-8")
    inbox = (ADMIN_DIR / "inbox.html").read_text(encoding="utf-8")
    assert "../js/api.js?v=20260818_2" in dashboard
    assert "../js/azure-auth.js?v=20260818_2" in dashboard
    assert "../js/api.js?v=20260818_4" in inbox
    assert "../js/azure-auth.js?v=20260818_2" in inbox


def test_hr_inbox_loads_persisted_comment_threads():
    inbox = (ADMIN_DIR / "inbox.html").read_text(encoding="utf-8")
    assert "window.apiGetComments" in inbox
    assert "await getCommentsFn(t.id)" in inbox
    assert "commentSets[index]" in inbox


def test_hr_reply_does_not_claim_a_client_side_identity():
    inbox = (ADMIN_DIR / "inbox.html").read_text(encoding="utf-8")
    reply = inbox[inbox.index("async function sendReply") :]
    assert "postFn(selectedTicketId, text)" in reply
    assert "postFn(selectedTicketId, text, loggedInUser)" not in reply
