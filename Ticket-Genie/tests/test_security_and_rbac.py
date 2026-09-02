"""Unit & Integration Tests for Security, JWT Verification, and Database RBAC."""

import base64
import json
import time
import unittest
from unittest.mock import MagicMock, patch

from services.jwt_verifier import (
    base64url_decode,
    parse_jwt_claims_unverified,
    verify_azure_jwt,
    verify_azure_user,
)
from services.sql_context_service import (
    SQLValidationError,
    validate_and_sanitize_sql,
)


def create_mock_jwt(payload_dict: dict, expired: bool = False) -> str:
    """Helper to generate an unverified mock JWT string for testing."""
    header = {"alg": "RS256", "typ": "JWT", "kid": "mock-key-1"}

    payload = payload_dict.copy()
    now = int(time.time())
    payload["iat"] = now - 60
    payload["exp"] = now - 100 if expired else now + 3600

    def encode_dict(d):
        json_bytes = json.dumps(d).encode("utf-8")
        return base64.urlsafe_b64encode(json_bytes).decode("utf-8").rstrip("=")

    header_str = encode_dict(header)
    payload_str = encode_dict(payload)
    signature_str = "mock_signature_bytes"

    return f"{header_str}.{payload_str}.{signature_str}"


class TestJWTVerifierAndSecurity(unittest.TestCase):
    """Test suite for JWT decoding, signature verification, and FastAPI dependency."""

    def test_base64url_decode(self):
        encoded = "SGVsbG8gV29ybGQ"  # 'Hello World' base64url without padding
        decoded = base64url_decode(encoded).decode("utf-8")
        self.assertEqual(decoded, "Hello World")

    def test_parse_jwt_claims_unverified(self):
        token = create_mock_jwt({"oid": "test-oid-123", "sub": "test-sub"})
        header, payload = parse_jwt_claims_unverified(token)
        self.assertEqual(header.get("kid"), "mock-key-1")
        self.assertEqual(payload.get("oid"), "test-oid-123")

    def test_verify_azure_jwt_expired_token(self):
        expired_token = create_mock_jwt({"oid": "test-oid-123"}, expired=True)
        from fastapi import HTTPException

        with self.assertRaises(HTTPException) as ctx:
            verify_azure_jwt(expired_token)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("expired", ctx.exception.detail.lower())

    def test_verify_azure_user_dev_fallback(self):
        with patch.dict("os.environ", {"AZURE_CLIENT_ID": ""}):
            from fastapi import HTTPException

            with self.assertRaises(HTTPException) as ctx:
                verify_azure_user(authorization=None)
            self.assertEqual(ctx.exception.status_code, 401)

    def test_verify_azure_user_missing_header_in_prod(self):
        with patch.dict("os.environ", {"AZURE_CLIENT_ID": "mock-client-id"}):
            from fastapi import HTTPException

            with self.assertRaises(HTTPException) as ctx:
                verify_azure_user(authorization=None)
            self.assertEqual(ctx.exception.status_code, 401)


class TestDatabaseRBACSafety(unittest.TestCase):
    """Test suite for Database RBAC query sanitization and scoping."""

    def test_forbidden_sql_operations_blocked(self):
        forbidden_queries = [
            "DELETE FROM tickets WHERE id = 'HD-1024'",
            "DROP TABLE tickets",
            "ALTER TABLE tickets DROP COLUMN priority",
            "TRUNCATE TABLE tickets",
            "GRANT ALL ON tickets TO public",
        ]
        for query in forbidden_queries:
            with self.assertRaises(SQLValidationError):
                validate_and_sanitize_sql(query, role="Employee", user_id="user-1")

    def test_employee_select_scoping(self):
        query = "SELECT * FROM tickets"
        sanitized = validate_and_sanitize_sql(query, role="Employee", user_id="user-1")
        self.assertIn("is_anonymous", sanitized)
        self.assertIn("user-1", sanitized)

    def test_hr_admin_select_scoping(self):
        query = "SELECT * FROM tickets"
        sanitized = validate_and_sanitize_sql(query, role="HR Admin", user_id="user-hr")
        self.assertIn("department = 'HR Team'", sanitized)

    def test_super_admin_unscoped_select(self):
        query = "SELECT * FROM tickets"
        sanitized = validate_and_sanitize_sql(
            query, role="Super Admin", user_id="admin-1"
        )
        self.assertEqual(sanitized, "SELECT * FROM tickets")

    def test_unauthorized_table_update_blocked(self):
        query = "UPDATE department_users SET role = 'Super Admin' WHERE id = '1'"
        with self.assertRaises(SQLValidationError):
            validate_and_sanitize_sql(query, role="Super Admin", user_id="admin-1")


class TestSuperAdminRoleManagement(unittest.TestCase):
    """Test suite for Admin role management & 403 Forbidden enforcement."""

    def test_require_super_admin_enforcement(self):
        from fastapi import HTTPException

        from api.admin import require_super_admin

        # Non-Admin roles (Employee, Ticketer, Member) must raise HTTP 403 Forbidden for admin routes
        non_admin_roles = [
            {"role": "Employee", "is_dev": False},
            {"role": "Ticketer", "is_dev": False},
            {"role": "Member", "is_dev": False},
        ]
        for user_ctx in non_admin_roles:
            with self.assertRaises(HTTPException) as ctx:
                require_super_admin(user_ctx)
            self.assertEqual(ctx.exception.status_code, 403)
            self.assertIn("forbidden", ctx.exception.detail.lower())

        # Admin role must pass without raising exception
        admin_ctx = {"role": "Admin", "is_dev": False}
        try:
            require_super_admin(admin_ctx)
        except Exception:
            self.fail("require_super_admin raised exception for valid Admin role!")

    def test_canonical_three_roles_helpers(self):
        from services.role_service import (
            EMPLOYEE_ASSIGNMENT_ROLES,
            is_admin,
            is_employee,
            is_ticket_mutation_authorized,
            is_ticketer,
        )

        self.assertIn("Employee", EMPLOYEE_ASSIGNMENT_ROLES)
        self.assertIn("Ticketer", EMPLOYEE_ASSIGNMENT_ROLES)
        self.assertIn("Admin", EMPLOYEE_ASSIGNMENT_ROLES)

        # Admin permissions
        self.assertTrue(is_admin("Admin"))
        self.assertTrue(is_ticketer("Admin"))
        self.assertTrue(is_ticket_mutation_authorized("Admin"))

        # Ticketer permissions
        self.assertFalse(is_admin("Ticketer"))
        self.assertTrue(is_ticketer("Ticketer"))
        self.assertTrue(is_ticket_mutation_authorized("Ticketer"))

        # Employee permissions
        self.assertFalse(is_admin("Employee"))
        self.assertFalse(is_ticketer("Employee"))
        self.assertTrue(is_employee("Employee"))
        self.assertFalse(is_ticket_mutation_authorized("Employee"))

    def test_department_user_role_crud(self):
        from database.crud import (
            add_department_user,
            list_department_users,
            remove_department_user,
        )

        test_dept = "Cybersecurity Operations"
        test_oid = "9a8b7c6d-5e4f-3a2b-1c0d-ef1234567890"
        test_role = "Security Lead"

        # 1. Create mapping in department_users table
        created = add_department_user(
            department_name=test_dept,
            azure_object_id=test_oid,
            role=test_role,
            user_email="sec.lead@ticketgenie.com",
        )
        self.assertEqual(created["department_name"], test_dept)
        self.assertEqual(created["azure_object_id"], test_oid)
        self.assertEqual(created["role"], test_role)

        # 2. List mappings from DB and verify inclusion
        users = list_department_users(department_name=test_dept)
        oids = [u["azure_object_id"] for u in users]
        self.assertIn(test_oid, oids)

        # 3. Delete mapping from DB and verify removal
        removed = remove_department_user(
            department_name=test_dept, azure_object_id=test_oid
        )
        self.assertTrue(removed)

        users_after = list_department_users(department_name=test_dept)
        oids_after = [u["azure_object_id"] for u in users_after]
        self.assertNotIn(test_oid, oids_after)

    def test_context_aware_and_department_rbac(self):
        from backend.api.tickets import list_tickets

        mock_db = MagicMock()
        admin_user = {
            "oid": "admin-oid-999",
            "email": "it.admin@company.com",
            "role": "IT Admin",
            "department": "IT Team",
        }

        # 1. Employee view (admin_view=False): Admin sees ONLY their own tickets (effective_requester = admin-oid-999)
        with patch("backend.api.tickets.get_all_tickets") as mock_get_tickets:
            mock_get_tickets.return_value = [
                {"id": "HD-999", "requester_id": "admin-oid-999"}
            ]
            tickets = list_tickets(
                admin_view=False, db=mock_db, current_user=admin_user
            )
            mock_get_tickets.assert_called_once_with(
                status=None,
                priority=None,
                search=None,
                requester_id="admin-oid-999",
                department=None,
                assigned_to=None,
                db=mock_db,
            )
            self.assertEqual(len(tickets), 1)

        # 2. Admin view (admin_view=True): Department admin ONLY sees tickets in their department ("IT Team")
        with patch("backend.api.tickets.get_all_tickets") as mock_get_tickets:
            mock_get_tickets.return_value = [{"id": "HD-100", "department": "IT Team"}]
            tickets = list_tickets(admin_view=True, db=mock_db, current_user=admin_user)
            mock_get_tickets.assert_called_once_with(
                status=None,
                priority=None,
                search=None,
                requester_id=None,
                department="IT Team",
                assigned_to=None,
                db=mock_db,
            )
            self.assertEqual(len(tickets), 1)


class TestCreatorTicketResolutionRestriction(unittest.TestCase):
    """Test suite ensuring users cannot resolve tickets they created themselves."""

    def test_creator_cannot_resolve_own_ticket(self):
        from fastapi import HTTPException

        from api.tickets import handle_update_ticket
        from models.ticket import TicketUpdate

        mock_ticket = {
            "id": "HD-101",
            "title": "My Laptop Is Slow",
            "description": "Laptop running slowly after update.",
            "status": "Open",
            "requester_id": "usr-creator-123",
            "category": "IT Support",
            "priority": "Medium",
            "department": "IT Team",
            "date": "2026-08-18",
            "createdAt": "2026-08-18T10:00:00",
        }
        current_user = {
            "oid": "usr-creator-123",
            "email": "creator@company.com",
            "role": "Employee",
        }

        with patch("api.tickets.get_ticket_by_id", return_value=mock_ticket):
            with self.assertRaises(HTTPException) as ctx:
                handle_update_ticket(
                    ticket_id="HD-101",
                    ticket_update=TicketUpdate(status="Resolved"),
                    db=MagicMock(),
                    current_user=current_user,
                )
            self.assertEqual(ctx.exception.status_code, 403)
            self.assertEqual(
                ctx.exception.detail, "You cannot resolve tickets you created."
            )

    def test_creator_cannot_close_own_ticket(self):
        from fastapi import HTTPException

        from api.tickets import handle_update_ticket
        from models.ticket import TicketUpdate

        mock_ticket = {
            "id": "HD-102",
            "title": "Need Monitor",
            "description": "Need a second monitor for setup.",
            "status": "Open",
            "requester_id": "usr-creator-123",
            "category": "IT Support",
            "priority": "Medium",
            "department": "IT Team",
            "date": "2026-08-18",
            "createdAt": "2026-08-18T10:00:00",
        }
        current_user = {
            "oid": "usr-creator-123",
            "email": "creator@company.com",
            "role": "Super Admin",
        }

        with patch("api.tickets.get_ticket_by_id", return_value=mock_ticket):
            with self.assertRaises(HTTPException) as ctx:
                handle_update_ticket(
                    ticket_id="HD-102",
                    ticket_update=TicketUpdate(status="Closed"),
                    db=MagicMock(),
                    current_user=current_user,
                )
            self.assertEqual(ctx.exception.status_code, 403)

    def test_non_creator_can_resolve_ticket(self):
        from api.tickets import handle_update_ticket
        from models.ticket import TicketUpdate

        mock_ticket = {
            "id": "HD-103",
            "title": "VPN Setup Issue",
            "description": "Cannot connect to VPN",
            "status": "Open",
            "requester_id": "usr-employee-456",
            "category": "IT Support",
            "priority": "Medium",
            "department": "IT Team",
            "date": "2026-08-18",
            "createdAt": "2026-08-18T10:00:00",
        }
        current_user = {
            "oid": "usr-support-789",
            "email": "support@company.com",
            "role": "IT Admin",
        }

        resolved_ticket = {**mock_ticket, "status": "Resolved"}
        with patch("api.tickets.get_ticket_by_id", return_value=mock_ticket):
            with patch("api.tickets.update_ticket", return_value=resolved_ticket):
                res = handle_update_ticket(
                    ticket_id="HD-103",
                    ticket_update=TicketUpdate(status="Resolved"),
                    db=MagicMock(),
                    current_user=current_user,
                )
                self.assertEqual(res["status"], "Resolved")

    def test_creator_can_update_other_fields(self):
        from api.tickets import handle_update_ticket
        from models.ticket import TicketUpdate

        mock_ticket = {
            "id": "HD-104",
            "title": "Keyboard Key Stuck",
            "description": "Letter A key is stuck",
            "status": "Open",
            "requester_id": "usr-creator-123",
            "category": "IT Support",
            "priority": "Low",
            "department": "IT Team",
            "date": "2026-08-18",
            "createdAt": "2026-08-18T10:00:00",
        }
        current_user = {
            "oid": "usr-creator-123",
            "email": "creator@company.com",
            "role": "Employee",
        }

        updated_ticket = {**mock_ticket, "priority": "High"}
        with patch("api.tickets.get_ticket_by_id", return_value=mock_ticket):
            with patch("api.tickets.update_ticket", return_value=updated_ticket):
                res = handle_update_ticket(
                    ticket_id="HD-104",
                    ticket_update=TicketUpdate(priority="High"),
                    db=MagicMock(),
                    current_user=current_user,
                )
                self.assertEqual(res["priority"], "High")

    def test_update_ticket_tool_blocks_creator_resolution(self):
        from agents.tool_registry import update_ticket_tool

        mock_ticket = {
            "id": "HD-105",
            "title": "Software Request",
            "description": "Requesting Figma license",
            "status": "Open",
            "requester_id": "usr-creator-123",
        }

        with patch("database.crud.get_ticket_by_id", return_value=mock_ticket):
            res = update_ticket_tool(
                ticket_id="HD-105",
                field="status",
                value="Resolved",
                user_id="usr-creator-123",
            )
            self.assertIn("Forbidden", res)
            self.assertIn("You cannot resolve tickets you created", res)


if __name__ == "__main__":
    unittest.main()
