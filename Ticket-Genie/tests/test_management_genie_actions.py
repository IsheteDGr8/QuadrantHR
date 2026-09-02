"""
Genie management-action tests: reassign_ticket / change_priority /
create_portal_employee (see backend/services/management_action_service.py).

Same convention as tests/test_chatbot.py - GPT's structured decision is
supplied directly via a FakeAIService rather than making a live call, since
what's under test is the deterministic authorization/validation/ambiguity-
resolution logic built on top of it, not GPT itself. database.crud reads/
writes that would touch the shared sqlite file are monkeypatched to keep
these tests fast, deterministic, and isolated from the large pre-existing
seed dataset - except for two explicit end-to-end tests that intentionally
exercise the real update_ticket_tool -> database path.
"""

import uuid

from agents.chatbot_agent import (
    ChatActionType,
    ChatbotDecision,
    ManagementActionFields,
)
from database.crud import create_ticket, get_ticket_by_id
from models.chatbot import (
    ChatIntent,
    ChatRequest,
    ChatScope,
    PendingManagementAction,
    TicketCandidate,
)
from models.ticket import TicketCreate
from services import chatbot_service, management_action_service
from services.role_service import resolve_visibility_scope


class FakeAIService:
    def __init__(self, decision):
        self.decision = decision
        self.calls = []

    def generate(self, *, system_prompt, user_content, response_model):
        self.calls.append((system_prompt, user_content, response_model))
        return self.decision


def ask_mgmt(message, *, decision, current_user, pending_action=None, **kwargs):
    request = ChatRequest(message=message, pending_action=pending_action, **kwargs)
    return chatbot_service.handle_message(
        request, current_user=current_user, ai_service=FakeAIService(decision)
    )


def _decision(intent, action_type=ChatActionType.MANAGEMENT_ACTION, **fields):
    return ChatbotDecision(
        scope=ChatScope.WORKPLACE,
        intent=intent,
        action=action_type,
        message="",
        management_fields=ManagementActionFields(**fields) if fields else None,
    )


def _candidate(id_, title, department="IT Team", priority="Medium", status="Open"):
    return TicketCandidate(
        id=id_, title=title, department=department, priority=priority, status=status
    )


# ADMIN_USER is scoped to IT Team - a Department-Admin-tier role with a
# department that DOES map cleanly to the ticket-department vocabulary
# (see role_service.ASSIGNMENT_TO_TICKET_DEPARTMENT). Tests that need a
# different/unmappable/missing scope construct their own current_user.
ADMIN_USER = {
    "role": "Admin",
    "oid": "admin-1",
    "email": "admin@co.com",
    "department": "IT Team",
}
HR_ADMIN_USER = {
    "role": "Department Admin",
    "oid": "hr-1",
    "email": "hr@co.com",
    "department": "HR Team",
}
NO_DEPARTMENT_ADMIN_USER = {
    "role": "Admin",
    "oid": "nodept-1",
    "email": "nodept@co.com",
}
UNMAPPABLE_DEPARTMENT_ADMIN_USER = {
    "role": "Admin",
    "oid": "um-1",
    "email": "um@co.com",
    "department": "Upper Executive Management",
}
SUPER_ADMIN_USER = {"role": "Super Admin", "oid": "sa-1", "email": "sa@co.com"}
EMPLOYEE_USER = {"role": "Employee", "oid": "emp-1", "email": "emp@co.com"}
MEMBER_USER = {"role": "Member", "oid": "mem-1", "email": "mem@co.com"}


def _make_real_ticket(department="IT Team", priority="Medium", title=None):
    # create_ticket() treats a matching title+description within 5 seconds
    # as a duplicate resubmission and reuses the earlier ticket instead of
    # making a new one (see database/crud.py) - a real title/description
    # per call keeps these fast-running tests from silently colliding.
    unique = uuid.uuid4().hex[:8]
    result = create_ticket(
        TicketCreate(
            title=title or f"Zzq test ticket {unique}",
            description=f"A distinctive test description {unique}.",
            department=department,
            priority=priority,
        )
    )
    return result["id"]


def fake_get_all_tickets_by_department(**kw):
    """Deterministic stand-in for database.crud.get_all_tickets that mimics
    its real department filtering (unlike a plain-list stub), so scoping
    tests never depend on the large shared seed dataset."""
    fixed = [
        {
            "id": "HD-7001",
            "title": "IT hardware ticket",
            "department": "IT Team",
            "priority": "Medium",
            "status": "Open",
        },
        {
            "id": "HD-7002",
            "title": "HR onboarding ticket",
            "department": "HR Team",
            "priority": "Medium",
            "status": "Open",
        },
    ]
    dept = kw.get("department")
    return [t for t in fixed if t["department"] == dept] if dept else fixed


# ---------------------------------------------------------------------------
# DEPARTMENT CHANGE
# ---------------------------------------------------------------------------


def test_reassign_ticket_unambiguous_updates_real_ticket():
    # Ticket starts in ADMIN_USER's own scope (IT Team) - a caller can only
    # act on a ticket that's currently within their authorized visibility,
    # then move it elsewhere.
    ticket_id = _make_real_ticket(department="IT Team")
    decision = _decision(ChatIntent.REASSIGN_TICKET, target_department="HR Team")
    response = ask_mgmt(
        f"Move {ticket_id} to HR",
        decision=decision,
        current_user=ADMIN_USER,
        pending_action=PendingManagementAction(
            action_type=ChatIntent.REASSIGN_TICKET, ticket_id=ticket_id
        ),
    )
    assert response.pending_action is None
    assert "Done." in response.message
    assert "HR Team" in response.message
    assert response.action.type == "refresh_ticket"
    assert response.action.ticket_id == ticket_id
    assert get_ticket_by_id(ticket_id)["department"] == "HR Team"


def test_reassign_ticket_missing_ticket_asks_with_candidates(monkeypatch):
    candidates = [
        _candidate("HD-2001", "VPN connection issue"),
        _candidate("HD-2002", "Badge access problem"),
    ]
    monkeypatch.setattr(
        management_action_service,
        "get_all_tickets",
        lambda **kw: [
            {
                "id": c.id,
                "title": c.title,
                "department": c.department,
                "priority": c.priority,
                "status": c.status,
            }
            for c in candidates
        ],
    )
    called = []
    monkeypatch.setattr(
        management_action_service,
        "execute_tool",
        lambda *a, **kw: called.append((a, kw)) or "Success",
    )

    decision = _decision(ChatIntent.REASSIGN_TICKET, target_department="IT Team")
    response = ask_mgmt(
        "Move this ticket to IT", decision=decision, current_user=ADMIN_USER
    )

    assert not called
    assert response.pending_action is not None
    assert response.pending_action.awaiting == "ticket_selection"
    assert "Which ticket" in response.message
    ids = {c.id for c in response.ticket_candidates}
    assert ids == {"HD-2001", "HD-2002"}
    assert all(c.title for c in response.ticket_candidates)


def test_reassign_ticket_multiple_matches_no_guessing(monkeypatch):
    candidates = [
        _candidate("HD-3001", "Printer offline"),
        _candidate("HD-3002", "Printer jam"),
    ]
    monkeypatch.setattr(
        management_action_service,
        "get_all_tickets",
        lambda **kw: [
            {
                "id": c.id,
                "title": c.title,
                "department": c.department,
                "priority": c.priority,
                "status": c.status,
            }
            for c in candidates
        ],
    )
    called = []
    monkeypatch.setattr(
        management_action_service,
        "execute_tool",
        lambda *a, **kw: called.append(1) or "Success",
    )

    decision = _decision(ChatIntent.REASSIGN_TICKET, target_department="IT Team")
    response = ask_mgmt(
        "Move the printer ticket to IT", decision=decision, current_user=ADMIN_USER
    )

    assert not called
    assert response.pending_action.awaiting == "ticket_selection"
    assert len(response.ticket_candidates) == 2


def test_reassign_ticket_invalid_department_asks_again(monkeypatch):
    called = []
    monkeypatch.setattr(
        management_action_service,
        "execute_tool",
        lambda *a, **kw: called.append(1) or "Success",
    )

    decision = _decision(ChatIntent.REASSIGN_TICKET, target_department="Mars Colony")
    response = ask_mgmt(
        "Move it there",
        decision=decision,
        current_user=ADMIN_USER,
        pending_action=PendingManagementAction(
            action_type=ChatIntent.REASSIGN_TICKET,
            ticket_id="HD-9001",
            ticket_title="Some ticket",
        ),
    )

    assert not called
    assert response.pending_action is not None
    assert response.pending_action.target_department is None
    assert "Which department" in response.message
    for dept in (
        "HR Team",
        "Accounting Team",
        "Workplace Operations Team",
        "IT Team",
        "Upper Management",
    ):
        assert dept in response.message


def test_reassign_ticket_employee_role_denied():
    decision = _decision(
        ChatIntent.REASSIGN_TICKET, ticket_id="HD-1001", target_department="IT Team"
    )
    response = ask_mgmt(
        "Move HD-1001 to IT", decision=decision, current_user=EMPLOYEE_USER
    )
    assert response.pending_action is None
    assert "isn't authorized" in response.message.lower()


def test_reassign_ticket_member_role_denied():
    decision = _decision(
        ChatIntent.REASSIGN_TICKET, ticket_id="HD-1001", target_department="IT Team"
    )
    response = ask_mgmt(
        "Move HD-1001 to IT", decision=decision, current_user=MEMBER_USER
    )
    assert "isn't authorized" in response.message.lower()


# ---------------------------------------------------------------------------
# PRIORITY CHANGE
# ---------------------------------------------------------------------------


def test_change_priority_unambiguous_updates_real_ticket():
    ticket_id = _make_real_ticket(priority="High")
    decision = _decision(ChatIntent.CHANGE_PRIORITY, target_priority="Low")
    response = ask_mgmt(
        f"Make {ticket_id} Low priority",
        decision=decision,
        current_user=ADMIN_USER,
        pending_action=PendingManagementAction(
            action_type=ChatIntent.CHANGE_PRIORITY, ticket_id=ticket_id
        ),
    )
    assert response.pending_action is None
    assert "Done." in response.message
    assert "Low" in response.message
    assert response.action.type == "refresh_ticket"
    assert response.action.ticket_id == ticket_id
    assert get_ticket_by_id(ticket_id)["priority"] == "Low"


def test_change_priority_missing_ticket_shows_current_priority(monkeypatch):
    candidates = [
        _candidate("HD-4001", "Laptop replacement request", priority="High"),
        _candidate("HD-4002", "Payroll correction", priority="Medium"),
    ]
    monkeypatch.setattr(
        management_action_service,
        "get_all_tickets",
        lambda **kw: [
            {
                "id": c.id,
                "title": c.title,
                "department": c.department,
                "priority": c.priority,
                "status": c.status,
            }
            for c in candidates
        ],
    )
    decision = _decision(ChatIntent.CHANGE_PRIORITY, target_priority="Low")
    response = ask_mgmt(
        "Reprioritize a ticket", decision=decision, current_user=ADMIN_USER
    )

    assert response.pending_action.awaiting == "ticket_selection"
    assert "HD-4001" in response.message and "High" in response.message
    assert "HD-4002" in response.message and "Medium" in response.message


def test_change_priority_multiple_matches_no_guessing(monkeypatch):
    candidates = [
        _candidate("HD-5001", "A", priority="High"),
        _candidate("HD-5002", "B", priority="High"),
    ]
    monkeypatch.setattr(
        management_action_service,
        "get_all_tickets",
        lambda **kw: [
            {
                "id": c.id,
                "title": c.title,
                "department": c.department,
                "priority": c.priority,
                "status": c.status,
            }
            for c in candidates
        ],
    )
    decision = _decision(ChatIntent.CHANGE_PRIORITY, target_priority="Low")
    response = ask_mgmt(
        "Move the high priority one to low", decision=decision, current_user=ADMIN_USER
    )
    assert response.pending_action.awaiting == "ticket_selection"
    assert len(response.ticket_candidates) == 2


def test_change_priority_invalid_priority_asks_again(monkeypatch):
    called = []
    monkeypatch.setattr(
        management_action_service,
        "execute_tool",
        lambda *a, **kw: called.append(1) or "Success",
    )
    decision = _decision(ChatIntent.CHANGE_PRIORITY, target_priority="Super Urgent")
    response = ask_mgmt(
        "bump it up",
        decision=decision,
        current_user=ADMIN_USER,
        pending_action=PendingManagementAction(
            action_type=ChatIntent.CHANGE_PRIORITY,
            ticket_id="HD-9002",
            ticket_title="Some ticket",
            current_priority="Medium",
        ),
    )
    assert not called
    assert response.pending_action.target_priority is None
    assert "priority" in response.message.lower()
    for p in ("Low", "Medium", "High", "Critical"):
        assert p in response.message


def test_change_priority_employee_role_denied():
    decision = _decision(
        ChatIntent.CHANGE_PRIORITY, ticket_id="HD-1001", target_priority="Low"
    )
    response = ask_mgmt(
        "Make HD-1001 low", decision=decision, current_user=EMPLOYEE_USER
    )
    assert response.pending_action is None
    assert "isn't authorized" in response.message.lower()


# ---------------------------------------------------------------------------
# EMPLOYEE CREATION
# ---------------------------------------------------------------------------


def _patch_departments(monkeypatch):
    monkeypatch.setattr(
        management_action_service,
        "list_departments",
        lambda: [
            {"name": n}
            for n in (
                "IT Team",
                "HR Team",
                "Accounting Team",
                "Upper Executive Management",
            )
        ],
    )


def test_create_employee_asks_only_missing_fields(monkeypatch):
    _patch_departments(monkeypatch)
    decision = _decision(ChatIntent.CREATE_PORTAL_EMPLOYEE)
    response = ask_mgmt(
        "Create a new employee", decision=decision, current_user=SUPER_ADMIN_USER
    )
    assert response.pending_action.awaiting == "employee_field:employee_name"
    assert "name" in response.message.lower()


def test_create_employee_missing_object_id_asks_and_does_not_create(monkeypatch):
    _patch_departments(monkeypatch)
    called = []
    monkeypatch.setattr(
        management_action_service, "add_department_user", lambda **kw: called.append(kw)
    )

    decision = _decision(
        ChatIntent.CREATE_PORTAL_EMPLOYEE,
        employee_name="Priya Shah",
        employee_email="priya@northstar.com",
        employee_department="IT Team",
        employee_role="Member",
    )
    response = ask_mgmt(
        "Add Priya Shah", decision=decision, current_user=SUPER_ADMIN_USER
    )

    assert not called
    assert response.pending_action.awaiting == "employee_field:employee_object_id"
    assert (
        "object id" in response.message.lower() or "entra" in response.message.lower()
    )


def test_create_employee_all_fields_gathered_shows_review_not_created(monkeypatch):
    _patch_departments(monkeypatch)
    called = []
    monkeypatch.setattr(
        management_action_service, "add_department_user", lambda **kw: called.append(kw)
    )

    decision = _decision(
        ChatIntent.CREATE_PORTAL_EMPLOYEE,
        employee_name="Priya Shah",
        employee_email="priya@northstar.com",
        employee_object_id="obj-123",
        employee_department="IT Team",
        employee_role="Member",
    )
    response = ask_mgmt(
        "here are all the details", decision=decision, current_user=SUPER_ADMIN_USER
    )

    assert not called
    assert response.pending_action.awaiting == "employee_confirmation"
    assert "Ready to create this portal assignment" in response.message
    assert "Priya Shah" in response.message


def test_create_employee_explicit_confirmation_creates(monkeypatch):
    _patch_departments(monkeypatch)
    called = []
    monkeypatch.setattr(
        management_action_service, "add_department_user", lambda **kw: called.append(kw)
    )

    pending = PendingManagementAction(
        action_type=ChatIntent.CREATE_PORTAL_EMPLOYEE,
        awaiting="employee_confirmation",
        employee_name="Priya Shah",
        employee_email="priya@northstar.com",
        employee_object_id="obj-123",
        employee_department="IT Team",
        employee_role="Member",
    )
    decision = _decision(ChatIntent.CREATE_PORTAL_EMPLOYEE)
    response = ask_mgmt(
        "yes, create it",
        decision=decision,
        current_user=SUPER_ADMIN_USER,
        pending_action=pending,
    )

    assert len(called) == 1
    assert called[0] == {
        "department_name": "IT Team",
        "azure_object_id": "obj-123",
        "role": "Member",
        "user_email": "priya@northstar.com",
    }
    assert response.pending_action is None
    assert "Done." in response.message


def test_create_employee_unauthorized_role_denied(monkeypatch):
    _patch_departments(monkeypatch)
    called = []
    monkeypatch.setattr(
        management_action_service, "add_department_user", lambda **kw: called.append(kw)
    )
    decision = _decision(ChatIntent.CREATE_PORTAL_EMPLOYEE)
    response = ask_mgmt(
        "Create a new employee", decision=decision, current_user=EMPLOYEE_USER
    )
    assert not called
    assert response.pending_action is None
    assert "isn't authorized" in response.message.lower()


def test_create_employee_never_bypasses_super_admin_requirement(monkeypatch):
    """Only an Admin role (or is_dev) may create a portal employee - Employee and Member fail here."""
    _patch_departments(monkeypatch)
    called = []
    monkeypatch.setattr(
        management_action_service, "add_department_user", lambda **kw: called.append(kw)
    )
    decision = _decision(ChatIntent.CREATE_PORTAL_EMPLOYEE)
    for role in (
        "Employee",
        "Member",
    ):
        response = ask_mgmt(
            "Create a new employee",
            decision=decision,
            current_user={"role": role, "oid": "x"},
        )
        assert "isn't authorized" in response.message.lower(), role
    assert not called


# ---------------------------------------------------------------------------
# MULTI-TURN CONTINUATION
# ---------------------------------------------------------------------------


def test_reassign_ticket_continuation_resolves_from_candidates(monkeypatch):
    candidates = [
        _candidate("HD-6001", "Badge access problem"),
        _candidate("HD-6002", "VPN connection issue"),
    ]
    monkeypatch.setattr(
        management_action_service,
        "get_all_tickets",
        lambda **kw: [
            {
                "id": c.id,
                "title": c.title,
                "department": c.department,
                "priority": c.priority,
                "status": c.status,
            }
            for c in candidates
        ],
    )
    called = []
    monkeypatch.setattr(
        management_action_service,
        "execute_tool",
        lambda name, args, **kw: called.append(args) or "Success: ok",
    )

    pending = PendingManagementAction(
        action_type=ChatIntent.REASSIGN_TICKET,
        awaiting="ticket_selection",
        target_department="IT Team",
        candidate_tickets=candidates,
    )
    decision = _decision(ChatIntent.REASSIGN_TICKET)
    response = ask_mgmt(
        "the VPN one",
        decision=decision,
        current_user=ADMIN_USER,
        pending_action=pending,
        active_intent=ChatIntent.REASSIGN_TICKET,
    )

    assert len(called) == 1
    assert called[0]["ticket_id"] == "HD-6002"
    assert response.pending_action is None
    assert "Done." in response.message


def test_change_priority_continuation_from_bare_ticket_id():
    ticket_id = _make_real_ticket(priority="Critical")
    pending = PendingManagementAction(
        action_type=ChatIntent.CHANGE_PRIORITY,
        awaiting="ticket_selection",
        target_priority="Low",
    )
    decision = _decision(ChatIntent.CHANGE_PRIORITY, ticket_id=ticket_id)
    response = ask_mgmt(
        ticket_id,
        decision=decision,
        current_user=ADMIN_USER,
        pending_action=pending,
        active_intent=ChatIntent.CHANGE_PRIORITY,
    )
    assert "Done." in response.message
    assert get_ticket_by_id(ticket_id)["priority"] == "Low"


# ---------------------------------------------------------------------------
# FAIL-CLOSED SCOPED VISIBILITY
# authorized-to-attempt-a-mutation (is_ticket_mutation_authorized) is a
# separate question from authorized-to-see-THIS-ticket
# (role_service.resolve_visibility_scope) - these tests cover the latter.
# ---------------------------------------------------------------------------


def test_resolve_visibility_scope_super_admin_is_unrestricted():
    scope = resolve_visibility_scope({"role": "Super Admin"})
    assert scope is not None
    assert scope.unrestricted is True
    assert scope.department is None


def test_resolve_visibility_scope_maps_known_departments():
    for dept in ("IT Team", "HR Team", "Accounting Team"):
        scope = resolve_visibility_scope({"role": "Admin", "department": dept})
        assert scope == (False, dept)


def test_resolve_visibility_scope_fails_closed_for_missing_department():
    assert resolve_visibility_scope({"role": "Admin"}) is None
    assert resolve_visibility_scope({"role": "Admin", "department": ""}) is None


def test_resolve_visibility_scope_fails_closed_for_unmappable_department():
    # "Upper Executive Management" is a real assignment-vocab department
    # (frontend/management/departments.html's #deptSelect) but has no
    # verified equivalent in the ticket-department vocabulary - see
    # role_service.ASSIGNMENT_TO_TICKET_DEPARTMENT's docstring.
    assert (
        resolve_visibility_scope(
            {"role": "Admin", "department": "Upper Executive Management"}
        )
        is None
    )


def test_resolve_visibility_scope_fails_closed_for_unknown_custom_role():
    # A free-text role from departments.html's "__custom__" option -
    # authorized-to-attempt is a separate gate (is_ticket_mutation_authorized
    # would already deny this), but the visibility resolver itself must
    # never grant org-wide access just because it doesn't recognize the role.
    scope = resolve_visibility_scope(
        {"role": "Regional Director", "department": "IT Team"}
    )
    assert scope == (False, "IT Team")  # department-scoped, NOT unrestricted
    assert resolve_visibility_scope({"role": "Regional Director"}) is None


def test_department_admin_scoped_to_it_cannot_see_hr_candidates(monkeypatch):
    monkeypatch.setattr(
        management_action_service, "get_all_tickets", fake_get_all_tickets_by_department
    )
    decision = _decision(
        ChatIntent.REASSIGN_TICKET, target_department="Accounting Team"
    )
    response = ask_mgmt(
        "Move a ticket to accounting",
        decision=decision,
        current_user={"role": "Department Admin", "department": "IT Team"},
    )
    ids = {c.id for c in response.ticket_candidates}
    assert "HD-7002" not in ids  # the HR ticket must never surface
    assert ids <= {"HD-7001"}


def test_department_admin_scoped_to_hr_cannot_mutate_it_ticket(monkeypatch):
    monkeypatch.setattr(
        management_action_service, "get_all_tickets", fake_get_all_tickets_by_department
    )
    called = []
    monkeypatch.setattr(
        management_action_service,
        "execute_tool",
        lambda *a, **kw: called.append(a) or "Success",
    )

    decision = _decision(
        ChatIntent.REASSIGN_TICKET,
        ticket_id="HD-7001",
        target_department="Accounting Team",
    )
    response = ask_mgmt(
        "Move HD-7001 to Accounting", decision=decision, current_user=HR_ADMIN_USER
    )

    assert not called
    # Never silently mutated - and never even offered as a candidate.
    if response.ticket_candidates:
        assert all(c.id != "HD-7001" for c in response.ticket_candidates)
    assert "Done." not in response.message


def test_unmappable_department_scope_fails_closed_not_org_wide(monkeypatch):
    monkeypatch.setattr(
        management_action_service, "get_all_tickets", fake_get_all_tickets_by_department
    )
    decision = _decision(ChatIntent.REASSIGN_TICKET, target_department="IT Team")
    response = ask_mgmt(
        "Move a ticket to IT",
        decision=decision,
        current_user=UNMAPPABLE_DEPARTMENT_ADMIN_USER,
    )
    assert response.pending_action is None
    assert response.ticket_candidates == []
    assert "couldn't determine your ticket scope" in response.message.lower()


def test_missing_department_scope_fails_closed(monkeypatch):
    monkeypatch.setattr(
        management_action_service, "get_all_tickets", fake_get_all_tickets_by_department
    )
    decision = _decision(ChatIntent.CHANGE_PRIORITY, target_priority="Low")
    response = ask_mgmt(
        "Reprioritize a ticket",
        decision=decision,
        current_user=NO_DEPARTMENT_ADMIN_USER,
    )
    assert response.pending_action is None
    assert response.ticket_candidates == []
    assert "couldn't determine your ticket scope" in response.message.lower()


def test_candidate_list_contains_only_authorized_tickets(monkeypatch):
    monkeypatch.setattr(
        management_action_service, "get_all_tickets", fake_get_all_tickets_by_department
    )
    decision = _decision(
        ChatIntent.REASSIGN_TICKET, target_department="Accounting Team"
    )
    response = ask_mgmt(
        "Move a ticket to accounting", decision=decision, current_user=HR_ADMIN_USER
    )
    assert response.ticket_candidates
    assert all(c.department == "HR Team" for c in response.ticket_candidates)


def test_forged_pending_action_ticket_id_cannot_bypass_scope(monkeypatch):
    """Even if a client replays/forges a pending_action whose ticket_id and
    ticket_title are already "resolved" to an out-of-scope ticket (so the
    normal candidate-resolution step would be skipped), the final
    pre-execution scope re-check must still catch it."""
    monkeypatch.setattr(
        management_action_service, "get_all_tickets", fake_get_all_tickets_by_department
    )
    called = []
    monkeypatch.setattr(
        management_action_service,
        "execute_tool",
        lambda *a, **kw: called.append(a) or "Success",
    )

    pending = PendingManagementAction(
        action_type=ChatIntent.REASSIGN_TICKET,
        ticket_id="HD-7001",
        ticket_title="IT hardware ticket",
        target_department="Accounting Team",
    )
    decision = _decision(ChatIntent.REASSIGN_TICKET)
    response = ask_mgmt(
        "go ahead",
        decision=decision,
        current_user=HR_ADMIN_USER,
        pending_action=pending,
    )

    assert not called
    assert response.pending_action is None
    assert "authorized" in response.message.lower()


def test_super_admin_can_see_and_mutate_ticket_outside_any_single_department(
    monkeypatch,
):
    monkeypatch.setattr(
        management_action_service, "get_all_tickets", fake_get_all_tickets_by_department
    )
    called = []
    monkeypatch.setattr(
        management_action_service,
        "execute_tool",
        lambda name, args, **kw: called.append(args) or "Success: ok",
    )
    decision = _decision(
        ChatIntent.REASSIGN_TICKET,
        ticket_id="HD-7002",
        target_department="Accounting Team",
    )
    response = ask_mgmt(
        "Move HD-7002 to Accounting", decision=decision, current_user=SUPER_ADMIN_USER
    )
    assert called and called[0]["ticket_id"] == "HD-7002"
    assert "Done." in response.message
