"""
Structural checks that Genie's navigation destinations agree with the LIVE
Svelte SPA, not just with what services/chatbot_service.py assumes.

There's no JS test runner in this repo (frontend/package.json only has
build/check/dev/preview - see tests/test_frontend_chatbot_wiring.py's
docstring for the same observation), so - matching that file's existing
pattern - these are content-level assertions on the actual current source:
frontend/src/App.svelte (the activeTab routing chain), frontend/src/
components/Sidebar.svelte (how a human reaches each destination), and
frontend/src/components/GenieAgentWidget.svelte (how Genie reaches the
same destinations). All three must agree, and none of them may reference
a legacy multi-page-app path.
"""

from pathlib import Path

FRONTEND_SRC = Path(__file__).resolve().parents[1] / "frontend" / "src"
APP_SVELTE = (FRONTEND_SRC / "App.svelte").read_text()
SIDEBAR_SVELTE = (FRONTEND_SRC / "components" / "Sidebar.svelte").read_text()
GENIE_WIDGET_SVELTE = (
    FRONTEND_SRC / "components" / "GenieAgentWidget.svelte"
).read_text()
# GenieAgentWidget.svelte (the floating popup) and views/GenieAIView.svelte
# (the full page) both share ONE conversation via lib/stores/genieChat.js -
# the nav-tab whitelist + role-gate re-check lives there once, not
# duplicated into either surface (see tests/test_genie_ai_page_wiring.py's
# module docstring for the full rationale).
GENIE_CHAT_STORE_JS = (FRONTEND_SRC / "lib" / "stores" / "genieChat.js").read_text()

# Every activeTab value Genie may navigate to today, per
# services/chatbot_service.py's _resolve_active_tab (the backend's
# deterministic NavigationTarget -> activeTab map).
GENIE_NAV_TABS = (
    "dashboard",
    "create-ticket",
    "inbox",
    "knowledge",
    "notifications",
    "announcements",
    "profile",
    "settings",
    "analytics",
    "onboarding",
)

STALE_PATH_FRAGMENTS = (
    ".html",
    "employee_NM",
    "management/",
    "admin_AV",
    "pages/management-portal",
)


def test_every_genie_nav_tab_is_actually_rendered_by_app_svelte():
    for tab in GENIE_NAV_TABS:
        assert f"'{tab}'" in APP_SVELTE, (
            f"App.svelte has no activeTab branch for {tab!r} - Genie would "
            "navigate to a tab that renders nothing"
        )


def test_genie_chat_store_whitelists_every_live_nav_tab():
    # Gated tabs appear as bare object keys (e.g. `inbox: isTicketer`), not
    # quoted strings, so match the raw tab name rather than requiring quotes.
    for tab in GENIE_NAV_TABS:
        assert tab in GENIE_CHAT_STORE_JS, (
            f"genieChat.js never references nav tab {tab!r}"
        )


def test_genie_chat_store_shares_the_sidebar_activetab_store():
    # Genie navigation (from either surface) and Sidebar navigation must
    # drive the SAME view state, not a second navigation mechanism.
    assert "from './tickets.js'" in GENIE_CHAT_STORE_JS
    assert "activeTab" in GENIE_CHAT_STORE_JS
    assert "from '../lib/stores/tickets.js'" in SIDEBAR_SVELTE
    assert "activeTab" in SIDEBAR_SVELTE
    assert "window.location" not in GENIE_WIDGET_SVELTE
    assert "window.location" not in GENIE_CHAT_STORE_JS


def test_genie_chat_store_reuses_the_existing_role_predicates_for_gated_tabs():
    # RBAC gating reuses the same isTicketer/isAdmin/isSuperAdmin
    # predicates Sidebar.svelte uses to hide its own nav items - not an
    # invented, independently-drifting role system.
    for predicate in ("isTicketer", "isAdmin", "isSuperAdmin"):
        assert predicate in GENIE_CHAT_STORE_JS
        assert predicate in SIDEBAR_SVELTE
    assert "from './auth.js'" in GENIE_CHAT_STORE_JS


def test_genie_widget_contains_no_stale_legacy_path_fragments():
    for fragment in STALE_PATH_FRAGMENTS:
        assert fragment not in GENIE_WIDGET_SVELTE, (
            f"GenieAgentWidget.svelte still references legacy path "
            f"fragment {fragment!r}"
        )


def test_app_svelte_contains_no_stale_legacy_path_fragments():
    for fragment in STALE_PATH_FRAGMENTS:
        assert fragment not in APP_SVELTE


def test_sidebar_svelte_contains_no_stale_legacy_path_fragments():
    for fragment in STALE_PATH_FRAGMENTS:
        assert fragment not in SIDEBAR_SVELTE
