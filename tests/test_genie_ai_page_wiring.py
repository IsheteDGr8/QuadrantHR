"""
Structural checks for the dedicated Genie AI full-page chat AND the
floating Genie popup, which now share one conversation.

There's no JS test runner in this repo (see tests/test_frontend_chatbot_wiring.py's
module docstring for the established precedent) - these are content-level
assertions on the actual Svelte/JS source files that ship in the live app.

Architecture under test: lib/stores/genieChat.js is the single source of
conversation state (conversationMessages, selectedConversationId,
sendingMessage, suggestions) and the single place sendMessage()/
applyGenieResponseActions() live. Both views/GenieAIView.svelte (full page)
and components/GenieAgentWidget.svelte (floating popup) import and call
those exact same exports - neither keeps its own history array, its own
selected-conversation id, or its own copy of the chatbot API call. Because
Svelte stores are module-level singletons, "both import the same store" IS
"both surfaces show the same conversation" - there is no separate runtime
wiring for that guarantee.
"""

from pathlib import Path

FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"
SIDEBAR_SVELTE = (FRONTEND_DIR / "src" / "components" / "Sidebar.svelte").read_text()
APP_SVELTE = (FRONTEND_DIR / "src" / "App.svelte").read_text()
GENIE_AI_VIEW = (FRONTEND_DIR / "src" / "views" / "GenieAIView.svelte").read_text()
GENIE_WIDGET_SVELTE = (
    FRONTEND_DIR / "src" / "components" / "GenieAgentWidget.svelte"
).read_text()
SRC_API_JS = (FRONTEND_DIR / "src" / "lib" / "api.js").read_text()
GENIE_CHAT_STORE_JS = (
    FRONTEND_DIR / "src" / "lib" / "stores" / "genieChat.js"
).read_text()
TICKET_STORE_JS = (FRONTEND_DIR / "src" / "lib" / "stores" / "tickets.js").read_text()


# ---------------------------------------------------------------------------
# Sidebar: Genie AI lives in the shared Employee section, for every role.
# ---------------------------------------------------------------------------


def test_sidebar_has_genie_ai_entry():
    assert "'genie-ai'" in SIDEBAR_SVELTE
    assert "Genie AI" in SIDEBAR_SVELTE


def test_sidebar_genie_ai_entry_is_inside_employee_section_not_gated_sections():
    employee_start = SIDEBAR_SVELTE.index("EMPLOYEE SECTION")
    dept_start = SIDEBAR_SVELTE.index("DEPARTMENT SECTION")
    employee_region = SIDEBAR_SVELTE[employee_start:dept_start]
    assert "'genie-ai'" in employee_region

    # Never inside the role-gated sections below Employee.
    for gated_marker in (
        "UPPER MANAGEMENT SECTION",
        "ADMIN SECTION",
    ):
        gated_start = SIDEBAR_SVELTE.index(gated_marker)
        gated_region = SIDEBAR_SVELTE[gated_start : gated_start + 1500]
        assert "'genie-ai'" not in gated_region


def test_sidebar_employee_section_order_matches_spec():
    employee_start = SIDEBAR_SVELTE.index("EMPLOYEE SECTION")
    dept_start = SIDEBAR_SVELTE.index("DEPARTMENT SECTION")
    employee_region = SIDEBAR_SVELTE[employee_start:dept_start]
    expected_order = [
        "'dashboard'",
        "'create-ticket'",
        "'announcements'",
        "'notifications'",
        "'genie-ai'",
        "'profile'",
    ]
    positions = [employee_region.index(tab) for tab in expected_order]
    assert positions == sorted(positions)
    assert "'knowledge'" not in employee_region


# ---------------------------------------------------------------------------
# App.svelte routing: Sidebar's "Genie AI" still opens the full page.
# ---------------------------------------------------------------------------


def test_app_svelte_imports_genie_ai_view():
    assert "import GenieAIView from './views/GenieAIView.svelte';" in APP_SVELTE


def test_sidebar_genie_ai_click_navigates_to_the_full_page():
    assert "$activeTab === 'genie-ai'" in APP_SVELTE
    idx = APP_SVELTE.index("$activeTab === 'genie-ai'")
    following = APP_SVELTE[idx : idx + 200]
    assert "<GenieAIView />" in following


# ---------------------------------------------------------------------------
# GenieAIView: history panel, new-chat control, reuse of the shared store.
# ---------------------------------------------------------------------------


def test_genie_ai_view_mount_only_refreshes_history_never_forces_new_chat():
    # Forcing startNewChat()/openConversation() on mount would wipe out
    # whatever conversation the user was already having in the floating
    # popup before navigating to this page - the whole point of sharing
    # genieChat.js's store is that arriving here must NOT reset it.
    onmount_start = GENIE_AI_VIEW.index("onMount(()")
    onmount_end = GENIE_AI_VIEW.index("});", onmount_start)
    onmount_body = GENIE_AI_VIEW[onmount_start:onmount_end]
    assert "loadConversations()" in onmount_body
    assert "startNewChat()" not in onmount_body
    assert "openConversation(" not in onmount_body


def test_genie_ai_view_has_new_chat_and_search_controls():
    assert "New Chat" in GENIE_AI_VIEW
    assert "Search chats..." in GENIE_AI_VIEW
    assert "handleNewChat" in GENIE_AI_VIEW
    assert "$searchQuery" in GENIE_AI_VIEW


def test_genie_ai_view_shows_empty_state_copy():
    assert "How can Genie help you today?" in GENIE_AI_VIEW


def test_genie_ai_view_has_no_history_rail_markup_duplicated_elsewhere():
    # The full history/search experience belongs only to the page, never
    # to the popup.
    assert "genie-history-panel" in GENIE_AI_VIEW
    assert "genie-history-panel" not in GENIE_WIDGET_SVELTE
    assert "Search chats..." not in GENIE_WIDGET_SVELTE


# ---------------------------------------------------------------------------
# Shared store: the ONE place conversation state + structured-action
# handling lives, used by both surfaces.
# ---------------------------------------------------------------------------


def test_genie_chat_store_sends_message_and_history_separately():
    # The message currently being sent must never also be duplicated as the
    # last entry of the history array sent alongside it.
    send_start = GENIE_CHAT_STORE_JS.index("export async function sendMessage")
    send_end = GENIE_CHAT_STORE_JS.index("\n}\n", send_start)
    body = GENIE_CHAT_STORE_JS[send_start:send_end]
    assert "historyForRequest" in body
    history_build_idx = body.index("historyForRequest =")
    push_idx = body.index("conversationMessages.update")
    assert history_build_idx < push_idx


def test_genie_chat_store_calls_the_real_chatbot_endpoint_via_api_js():
    assert "apiGenieChat" in GENIE_CHAT_STORE_JS
    assert "from '../api.js'" in GENIE_CHAT_STORE_JS


def test_genie_chat_store_never_erases_history_on_failure():
    send_start = GENIE_CHAT_STORE_JS.index("export async function sendMessage")
    catch_start = GENIE_CHAT_STORE_JS.index("catch (err)", send_start)
    catch_end = GENIE_CHAT_STORE_JS.index("finally", catch_start)
    catch_body = GENIE_CHAT_STORE_JS[catch_start:catch_end]
    assert "conversationMessages.set([])" not in catch_body
    assert "conversationMessages.update" in catch_body


def test_genie_chat_store_owns_structured_action_handling():
    # ready_for_review draft handoff, and role-gated navigation, live here
    # (not duplicated into either GenieAIView.svelte or GenieAgentWidget.svelte).
    assert "export function applyGenieResponseActions" in GENIE_CHAT_STORE_JS
    assert "genieDraftStore" in GENIE_CHAT_STORE_JS
    assert "ready_for_review" in GENIE_CHAT_STORE_JS
    assert "res.action.type === 'navigate'" in GENIE_CHAT_STORE_JS
    assert "NAV_TAB_ROLE_GATE" in GENIE_CHAT_STORE_JS
    assert "NAV_TABS" in GENIE_CHAT_STORE_JS
    assert "res.action.type === 'refresh_ticket'" in GENIE_CHAT_STORE_JS
    assert "refreshTicketState" in GENIE_CHAT_STORE_JS


def test_genie_chat_store_whitelists_every_nav_tab_with_role_predicates():
    for predicate in ("isTicketer", "isAdmin", "isSuperAdmin"):
        assert predicate in GENIE_CHAT_STORE_JS


def test_ticket_selection_persists_id_and_reconciles_from_fresh_api_data():
    assert "sessionStorage.setItem('selectedTicketId', ticket.id)" in TICKET_STORE_JS
    assert (
        "sessionStorage.setItem('selectedTicket', JSON.stringify(ticket))"
        not in TICKET_STORE_JS
    )
    assert "find((ticket) => ticket.id === selectedId)" in TICKET_STORE_JS
    assert "export async function refreshTicketState" in TICKET_STORE_JS


def test_conversation_endpoints_exist_in_api_js():
    assert "apiFetchGenieConversations" in SRC_API_JS
    assert "apiFetchGenieConversation" in SRC_API_JS
    assert "/chatbot/conversations" in SRC_API_JS


def test_genie_conversation_pdf_export_is_wired_to_both_request_paths():
    assert "apiExportGenieConversationPDF" in SRC_API_JS
    assert "/export" in SRC_API_JS
    assert "Download PDF" in GENIE_AI_VIEW
    assert "handleExportPdf" in GENIE_AI_VIEW
    assert "export_conversation_pdf" in GENIE_CHAT_STORE_JS
    assert "apiExportGenieConversationPDF" in GENIE_CHAT_STORE_JS


def test_api_js_still_sends_conversation_state_fields():
    for field in (
        "history",
        "draft",
        "active_intent",
        "active_request_type",
        "pending_action",
        "conversation_id",
    ):
        assert field in SRC_API_JS


# ---------------------------------------------------------------------------
# Both surfaces consume the SAME store - no local ad-hoc/shadow state.
# ---------------------------------------------------------------------------


def test_both_surfaces_import_conversation_state_from_the_same_store_file():
    shared_import = "from '../lib/stores/genieChat.js'"
    assert shared_import in GENIE_AI_VIEW
    assert shared_import in GENIE_WIDGET_SVELTE


def test_both_surfaces_call_sendmessage_and_the_shared_action_handler():
    for surface in (GENIE_AI_VIEW, GENIE_WIDGET_SVELTE):
        assert "sendMessage" in surface
        assert "applyGenieResponseActions" in surface


def test_neither_surface_shadows_conversation_state_with_a_local_copy():
    # Regression guard for the exact bug this change fixed: each surface
    # used to keep its own `let history = []` / `let messages = [...]`
    # array, so a message sent in one was invisible in the other.
    for surface, name in (
        (GENIE_AI_VIEW, "GenieAIView.svelte"),
        (GENIE_WIDGET_SVELTE, "GenieAgentWidget.svelte"),
    ):
        assert "writable(" not in surface, f"{name} must not declare its own store"
        assert "let history = []" not in surface, f"{name} must not shadow history"
        assert "let messages = [" not in surface, (
            f"{name} must not keep its own local messages array"
        )
        assert "apiGenieChat(" not in surface, (
            f"{name} must call the shared sendMessage(), not apiGenieChat() directly"
        )


def test_widget_toggle_only_toggles_open_state_never_touches_conversation():
    # Closing/reopening the popup must never reset or reload the
    # conversation - it's the same shared store, already in memory.
    toggle_start = GENIE_WIDGET_SVELTE.index("function toggleChat()")
    toggle_end = GENIE_WIDGET_SVELTE.index("}", toggle_start)
    toggle_body = GENIE_WIDGET_SVELTE[toggle_start:toggle_end]
    assert "isOpen = !isOpen" in toggle_body
    assert "startNewChat" not in toggle_body
    assert "openConversation" not in toggle_body


def test_new_chat_resets_the_one_shared_store_both_surfaces_read():
    # Confirms "New Chat on the page updates the popup too" structurally:
    # startNewChat() mutates the exact same conversationMessages/
    # selectedConversationId stores the popup subscribes to - there is no
    # separate reset path per surface.
    start = GENIE_CHAT_STORE_JS.index("export function startNewChat")
    end = GENIE_CHAT_STORE_JS.index("\n}\n", start)
    body = GENIE_CHAT_STORE_JS[start:end]
    assert "selectedConversationId.set(null)" in body
    assert "conversationMessages.set([])" in body


# ---------------------------------------------------------------------------
# Floating widget: compact popup drawer, never a page navigation.
# ---------------------------------------------------------------------------


def test_floating_widget_opens_a_compact_drawer_not_a_page_navigation():
    assert "isOpen = !isOpen" in GENIE_WIDGET_SVELTE
    assert "{#if isOpen}" in GENIE_WIDGET_SVELTE
    # The old page-launcher behavior must be gone.
    assert "$activeTab = 'genie-ai'" not in GENIE_WIDGET_SVELTE
    assert "from '../lib/stores/tickets.js'" not in GENIE_WIDGET_SVELTE


def test_floating_widget_has_compact_drawer_markup_not_history_rail():
    for marker in (
        "genie-chat-header",
        "genie-messages",
        "genie-input-area",
        "genie-close",
    ):
        assert marker in GENIE_WIDGET_SVELTE


def test_floating_widget_renders_suggestions_from_the_shared_store():
    assert "$suggestions" in GENIE_WIDGET_SVELTE


def test_both_genie_surfaces_show_the_professional_ai_disclaimer():
    disclaimer = (
        "Genie uses artificial intelligence and may provide inaccurate or incomplete "
        "information. Verify important details before acting."
    )
    assert disclaimer in GENIE_AI_VIEW
    assert disclaimer in GENIE_WIDGET_SVELTE
    assert 'role="note"' in GENIE_AI_VIEW
    assert 'role="note"' in GENIE_WIDGET_SVELTE


def test_floating_launcher_renders_on_normal_pages_but_not_on_genie_ai_page():
    # The launcher must render on every other page (e.g. dashboard,
    # create-ticket, ...) but be hidden specifically while the full Genie
    # AI page is active - otherwise a redundant popup floats over the page
    # that's already showing the same conversation full-size.
    assert "<GenieAgentWidget" in APP_SVELTE
    idx = APP_SVELTE.index("<GenieAgentWidget")
    preceding = APP_SVELTE[max(0, idx - 120) : idx]
    assert "{#if $activeTab !== 'genie-ai'}" in preceding


def test_sidebar_genie_ai_page_route_is_unaffected_by_the_launcher_guard():
    # The launcher visibility guard must not interfere with the Sidebar's
    # own "Genie AI" -> full page routing, which lives in a separate
    # {:else if} branch earlier in the same file.
    assert "$activeTab === 'genie-ai'" in APP_SVELTE
    nav_idx = APP_SVELTE.index("$activeTab === 'genie-ai'")
    following = APP_SVELTE[nav_idx : nav_idx + 200]
    assert "<GenieAIView />" in following
