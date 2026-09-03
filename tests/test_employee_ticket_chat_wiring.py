"""Structural regression checks for the employee ticket conversation page."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_JS = (ROOT / "frontend" / "js" / "api.js").read_text(encoding="utf-8")
EMPLOYEE_JS = (ROOT / "frontend" / "employee_NM" / "employee.js").read_text(
    encoding="utf-8"
)
DETAIL_HTML = (ROOT / "frontend" / "employee_NM" / "ticket-detail.html").read_text(
    encoding="utf-8"
)


def test_ticket_detail_loads_required_modules():
    for script in (
        "../js/api.js",
        "../js/azure-auth.js",
        "../js/theme.js",
        "employee.js",
    ):
        assert f'src="{script}?v=' in DETAIL_HTML


def test_ticket_detail_api_and_employee_modules_share_cache_version():
    assert 'src="../js/api.js?v=20260818_3"' in DETAIL_HTML
    assert 'src="employee.js?v=20260818_3"' in DETAIL_HTML


def test_ticket_detail_uses_direct_ticket_api_lookup():
    assert "async function apiFetchTicket(ticketId)" in API_JS
    assert "window.apiFetchTicket" in EMPLOYEE_JS
    detail_loader = EMPLOYEE_JS[
        EMPLOYEE_JS.index("async function loadTicketDetailPage") : EMPLOYEE_JS.index(
            "async function renderTicketCommentsThread"
        )
    ]
    assert "apiFetchTickets" not in detail_loader
    assert "tickets[0]" not in detail_loader


def test_ticket_detail_has_visible_failure_state():
    assert "function renderTicketDetailError" in EMPLOYEE_JS
    assert "Conversation unavailable" in EMPLOYEE_JS


def test_comment_api_rejects_unsuccessful_responses():
    get_comments = API_JS[API_JS.index("async function apiGetComments") :]
    assert "if (!res.ok) throw" in get_comments
    post_comments = API_JS[API_JS.index("async function apiPostComment") :]
    assert "if (!res.ok) throw" in post_comments


def test_reply_is_only_cleared_after_successful_post():
    reply = EMPLOYEE_JS[EMPLOYEE_JS.index("async function sendTicketReply") :]
    assert reply.index("await postFn") < reply.index('replyInput.value = ""')
    assert 'showNotification("Message sent."' in reply


def test_enter_key_sends_ticket_reply():
    assert 'event.key === "Enter"' in EMPLOYEE_JS
    assert "sendTicketReply(ticketId)" in EMPLOYEE_JS
