"""
Structural checks on the chatbot <-> current New Request UI integration.

frontend/employee_NM/new-request.html was redesigned with new form IDs
(standardTicketForm/standardSubject/standardDepartment/standardDescription,
leaveTicketForm/leaveTypeSelect/leaveStartDate/leaveEndDate/leaveDescription,
anonymousTicketForm/anonymousCategory/anonymousDescription) and its own
switchTab()/submitEmployeeStandardTicket() etc., while frontend/js/
script.js's chatbot integration used to target an older set of form IDs
(newTicketForm/ticketSubject/anonTicketForm/standardRequestTab/...) that
no longer exist on the page. These tests guard that the chatbot now
targets the CURRENT DOM, still talks to the real backend chatbot
endpoint, still never auto-submits, and that the Leave/Anonymous hard
rules (department_override, is_anonymous) are wired into the current
forms' own submit handlers (which now live inline in new-request.html,
not in script.js).

There's no JS test runner in this repo, so these are content-level
assertions on the actual served files.

frontend/js/script.js, frontend/employee_NM/, frontend/management/, and
frontend/admin_AV/ (SCRIPT_JS/NEW_REQUEST_HTML/MANAGEMENT_SUBMIT_HTML/
ADMIN_SUBMIT_HTML below) are now DEAD CODE from before the Svelte
migration: none of those directories sit under frontend/public/ (Vite's
only verbatim-copy source) and vite.config.js declares no multi-page
build.rollupOptions.input, so Vite's build only ever emits
frontend/index.html's own bundle - the Docker image's frontend stage
copies just that `dist/` output into nginx. The live app is a single-page
Svelte app (frontend/src/App.svelte switches between src/views/* by an
activeTab store, e.g. CreateTicketView.svelte for ticket creation); the
live Genie is frontend/src/components/GenieAgentWidget.svelte calling
frontend/src/lib/api.js's apiGenieChat(). The SCRIPT_JS/*_HTML-based
tests below are kept anyway per explicit instruction not to remove
still-useful legacy/backward-compatibility coverage - just be aware they
no longer describe what's actually deployed. The "Live Svelte frontend"
section further down covers the endpoint wiring that actually runs in
production.
"""

from pathlib import Path

FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"
SCRIPT_JS = (FRONTEND_DIR / "js" / "script.js").read_text()
NEW_REQUEST_HTML = (FRONTEND_DIR / "employee_NM" / "new-request.html").read_text()
MANAGEMENT_SUBMIT_HTML = (
    FRONTEND_DIR / "management" / "submit-ticket.html"
).read_text()
ADMIN_SUBMIT_HTML = (FRONTEND_DIR / "admin_AV" / "submit-ticket.html").read_text()
SRC_API_JS = (FRONTEND_DIR / "src" / "lib" / "api.js").read_text()
GENIE_WIDGET_SVELTE = (
    FRONTEND_DIR / "src" / "components" / "GenieAgentWidget.svelte"
).read_text()
# GenieAgentWidget.svelte is now just a floating launcher that switches
# activeTab to 'genie-ai' - it no longer calls apiGenieChat itself. That
# call, and the conversation-state tracking below, now live in the
# dedicated Genie AI page's store (see tests/test_genie_ai_page_wiring.py's
# module docstring for the full rationale).
GENIE_CHAT_STORE_JS = (
    FRONTEND_DIR / "src" / "lib" / "stores" / "genieChat.js"
).read_text()

OLD_STALE_IDS = (
    "newTicketForm",
    "ticketSubject",
    "ticketCategory",
    "anonTicketForm",
    "anonTicketSubject",
    "anonTicketCategory",
    "anonTicketDescription",
    "standardRequestTab",
    "anonymousRequestTab",
    "leaveRequestTab",
)


def test_genie_widget_calls_the_real_chatbot_endpoint():
    assert "/chatbot/message" in SCRIPT_JS


def test_genie_widget_no_longer_uses_the_legacy_genie_chat_endpoint():
    assert "/genie/chat" not in SCRIPT_JS


def test_no_local_static_genie_response_generator_remains():
    assert "getGenieResponse" not in SCRIPT_JS
    assert "apiGenieChat" not in SCRIPT_JS


def test_conversation_state_fields_are_sent_to_the_backend():
    for field in ("history", "draft", "active_intent", "active_request_type"):
        assert field in SCRIPT_JS
        assert field in SRC_API_JS


def test_genie_chat_store_tracks_and_sends_conversation_state():
    assert "apiGenieChat(trimmed" in GENIE_CHAT_STORE_JS
    assert "history" in GENIE_CHAT_STORE_JS
    assert "draft" in GENIE_CHAT_STORE_JS
    assert "active_intent" in GENIE_CHAT_STORE_JS
    assert "active_request_type" in GENIE_CHAT_STORE_JS


# ---------------------------------------------------------------------------
# Live Svelte frontend (frontend/src/lib/api.js + GenieAgentWidget.svelte) -
# the endpoint wiring that actually runs in the deployed app (see module
# docstring: frontend/js/script.js is not shipped by the Vite/Docker
# build). These tests guard the LIVE path directly, independent of
# whatever the legacy SCRIPT_JS-based tests above continue to assert.
# ---------------------------------------------------------------------------


def test_live_api_js_calls_the_real_chatbot_endpoint():
    assert "/api/chatbot/message" in SRC_API_JS


def test_live_api_js_chatbot_call_is_the_primary_send_path():
    # /api/chatbot/message must be tried first, not only reachable through
    # (or replaced by) the legacy /api/genie/chat fallback further down in
    # the same function.
    start = SRC_API_JS.index("export async function apiGenieChat")
    fallback_start = SRC_API_JS.index("/api/genie/chat", start)
    primary_region = SRC_API_JS[start:fallback_start]
    assert "/api/chatbot/message" in primary_region


def test_genie_chat_store_imports_and_uses_the_live_api_module():
    assert "from '../api.js'" in GENIE_CHAT_STORE_JS
    assert "apiGenieChat" in GENIE_CHAT_STORE_JS
    assert "apiGenieChat(trimmed" in GENIE_CHAT_STORE_JS


def test_genie_widget_does_not_depend_on_dead_legacy_script_js():
    # The live widget must send messages through the imported ES-module
    # apiGenieChat (frontend/src/lib/api.js) only - never through the dead
    # frontend/js/script.js or the unused legacy global from
    # frontend/public/js/api.js (loaded into global scope by index.html
    # but never wired into the Svelte app - see module docstring).
    assert "script.js" not in GENIE_WIDGET_SVELTE
    assert "public/js" not in GENIE_WIDGET_SVELTE
    assert "window.apiGenieChat" not in GENIE_WIDGET_SVELTE
    assert "getGenieResponse" not in GENIE_WIDGET_SVELTE


def test_form_opening_is_gated_on_ready_for_review():
    assert "ready_for_review" in SCRIPT_JS


def test_old_ui_ids_are_no_longer_required_by_the_chatbot():
    for stale_id in OLD_STALE_IDS:
        assert stale_id not in SCRIPT_JS, f"stale ID {stale_id!r} still referenced"


def test_prefill_targets_current_standard_form_fields():
    for current_id in ("standardSubject", "standardDescription", "standardDepartment"):
        assert current_id in SCRIPT_JS


def test_prefill_targets_current_leave_form_fields():
    for current_id in ("leaveTypeSelect", "leaveStartDate", "leaveDescription"):
        assert current_id in SCRIPT_JS


def test_prefill_targets_current_anonymous_form_fields():
    assert "anonymousDescription" in SCRIPT_JS


def test_all_three_request_types_map_to_the_current_switchTab_names():
    assert "GENIE_REQUEST_TYPE_TAB_NAMES" in SCRIPT_JS
    assert '"standard"' in SCRIPT_JS
    assert '"leave"' in SCRIPT_JS
    assert '"anonymous"' in SCRIPT_JS
    assert "window.switchTab" in SCRIPT_JS


def test_ready_draft_detection_uses_current_standard_form_id():
    assert 'getElementById("standardTicketForm")' in SCRIPT_JS
    assert 'getElementById("newTicketForm")' not in SCRIPT_JS


def test_chat_response_handling_never_calls_apiCreateTicket():
    # apiCreateTicket is only ever called from the current New Request
    # page's own submit handlers (user clicks the real submit button) -
    # never from the chatbot response-handling functions.
    handler_names = (
        "advanceGenieState",
        "openReadyDraft",
        "prefillRequestForm",
        "handleGenieAction",
        "apiChatbotMessage",
    )
    start = min(SCRIPT_JS.index(f"function {name}") for name in handler_names)
    end = SCRIPT_JS.index("// Bind all global utilities to window")
    assert end > start
    chat_handling_region = SCRIPT_JS[start:end]
    assert "apiCreateTicket(" not in chat_handling_region
    assert ".submit()" not in chat_handling_region
    assert "requestSubmitButton.click" not in chat_handling_region


# ---------------------------------------------------------------------------
# The current New Request page (submission logic now lives inline there,
# consistent with how submitEmployeeStandardTicket already worked)
# ---------------------------------------------------------------------------


def test_standard_form_has_stable_ids_and_submit_handler():
    for current_id in (
        "standardTicketForm",
        "standardSubject",
        "standardDepartment",
        "standardDescription",
        "submitStandardBtn",
    ):
        assert f'id="{current_id}"' in NEW_REQUEST_HTML
    assert "submitEmployeeStandardTicket" in NEW_REQUEST_HTML


def test_leave_form_has_stable_ids_and_submit_handler():
    for current_id in (
        "leaveTicketForm",
        "leaveTypeSelect",
        "leaveHandoverLead",
        "leaveStartDate",
        "leaveEndDate",
        "leaveDescription",
        "submitLeaveBtn",
    ):
        assert f'id="{current_id}"' in NEW_REQUEST_HTML
    assert "submitEmployeeLeaveTicket" in NEW_REQUEST_HTML


def test_anonymous_form_has_stable_ids_and_submit_handler():
    for current_id in (
        "anonymousTicketForm",
        "anonymousCategory",
        "anonymousDescription",
        "submitAnonymousBtn",
    ):
        assert f'id="{current_id}"' in NEW_REQUEST_HTML
    assert "submitEmployeeAnonymousTicket" in NEW_REQUEST_HTML


def test_leave_submission_sends_deterministic_department_override():
    assert "department_override: 'Upper Management'" in NEW_REQUEST_HTML


def test_anonymous_submission_sets_is_anonymous_true():
    assert "is_anonymous: true" in NEW_REQUEST_HTML


def test_standard_submission_preserves_auto_ai_classification_default():
    assert 'value="Auto"' in NEW_REQUEST_HTML
    assert "Auto (AI Classification)" in NEW_REQUEST_HTML


def test_all_three_forms_only_submit_on_explicit_user_submit_event():
    assert "submitEmployeeStandardTicket(event)" in NEW_REQUEST_HTML
    assert "submitEmployeeLeaveTicket(event)" in NEW_REQUEST_HTML
    assert "submitEmployeeAnonymousTicket(event)" in NEW_REQUEST_HTML


def test_current_tab_switch_mechanism_is_reused_not_duplicated():
    assert "function switchTab(tabType)" in NEW_REQUEST_HTML
    # script.js must not define a second, competing tab-switch mechanism.
    assert "function switchTab(" not in SCRIPT_JS
    assert "function switchRequestTab(" not in SCRIPT_JS


# ---------------------------------------------------------------------------
# Management/admin create-ticket handoff (Feature 4) - portal-aware prefill,
# targeting each portal's REAL current form ids rather than the employee
# form's ids, still never auto-submitting.
# ---------------------------------------------------------------------------


def test_management_submit_page_has_the_ids_genie_targets():
    for current_id in (
        "createTicketForm",
        "ticketTitle",
        "targetDepartment",
        "priorityLevel",
        "ticketDescription",
    ):
        assert f'id="{current_id}"' in MANAGEMENT_SUBMIT_HTML


def test_admin_submit_page_has_the_ids_genie_targets():
    for current_id in (
        "ticketForm",
        "ticketTitle",
        "category",
        "priority",
        "ticketDesc",
    ):
        assert f'id="{current_id}"' in ADMIN_SUBMIT_HTML


def test_portal_context_is_resolved_deterministically_not_by_gpt():
    assert "function getPortalContext()" in SCRIPT_JS
    assert '"/management/"' in SCRIPT_JS
    assert '"/admin_AV/"' in SCRIPT_JS


def test_prefill_dispatch_targets_each_portals_real_form_ids():
    assert "function prefillManagementForm(draft)" in SCRIPT_JS
    assert "function prefillAdminForm(draft)" in SCRIPT_JS
    assert "function prefillDraftIntoForm(" in SCRIPT_JS
    for management_id in (
        "ticketTitle",
        "ticketDescription",
        "targetDepartment",
        "priorityLevel",
    ):
        assert management_id in SCRIPT_JS
    assert "ticketDesc" in SCRIPT_JS
    # Employee-only ids must never leak into the management/admin prefill
    # functions - each portal's prefill only ever targets its own form.
    mgmt_start = SCRIPT_JS.index("function prefillManagementForm(draft)")
    mgmt_end = SCRIPT_JS.index("function prefillAdminForm(draft)")
    assert "standardSubject" not in SCRIPT_JS[mgmt_start:mgmt_end]


def test_management_and_admin_forms_are_never_auto_submitted_by_genie():
    handler_names = (
        "prefillManagementForm",
        "prefillAdminForm",
        "prefillDraftIntoForm",
        "openReadyDraft",
        "applyPendingGenieDraft",
    )
    start = min(SCRIPT_JS.index(f"function {name}") for name in handler_names)
    end = SCRIPT_JS.index("// Bind all global utilities to window")
    region = SCRIPT_JS[start:end]
    assert "apiCreateTicket(" not in region
    assert ".submit()" not in region


def test_draft_persists_across_navigation_for_every_portal():
    # Same sessionStorage handoff key/mechanism reused for every portal -
    # no separate/duplicate persistence path per portal.
    assert "GENIE_PENDING_DRAFT_KEY" in SCRIPT_JS
    assert "function applyPendingGenieDraft()" in SCRIPT_JS
    assert "prefillDraftIntoForm(pending.request_type, pending.draft)" in SCRIPT_JS


def test_navigation_to_new_request_resolves_to_each_portals_real_submit_page():
    assert '"new-request.html") return "submit-ticket.html"' in SCRIPT_JS
