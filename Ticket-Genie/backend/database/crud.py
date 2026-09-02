import os
from datetime import datetime, timedelta
from typing import List, Optional

from opentelemetry import trace
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from database.connection import SessionLocal
from database.models_db import TicketDB
from models.ticket import TicketCreate, TicketUpdate

tracer = trace.get_tracer("ticketgenie.database.crud")


def _generate_next_id(db: Session) -> str:
    highest = 1000
    try:
        records = db.query(TicketDB.id).all()
        for (tid,) in records:
            if tid and tid.startswith("HD-"):
                try:
                    num = int(tid.replace("HD-", ""))
                    if num > highest:
                        highest = num
                except ValueError:
                    pass
    except Exception:
        pass
    return f"HD-{highest + 1}"


def create_ticket(ticket: TicketCreate, db: Optional[Session] = None) -> dict:
    with tracer.start_as_current_span("database.create_ticket") as span:
        span.set_attribute("service.name", "database")
        span.set_attribute("service.method", "create_ticket")
        return _create_ticket_internal(ticket, db=db)


def _resolve_user_email(user_id: Optional[str], session: Session) -> Optional[str]:
    if not user_id or user_id.lower() in ("all", "user"):
        return None
    if "@" in user_id:
        return user_id.strip()
    try:
        from database.models_db import DepartmentUserDB, UserProfileDB

        uid_lower = user_id.lower().strip()
        prof = (
            session.query(UserProfileDB)
            .filter(
                or_(
                    func.lower(UserProfileDB.id) == uid_lower,
                    func.lower(UserProfileDB.email) == uid_lower,
                )
            )
            .first()
        )
        if prof and prof.email:
            return prof.email

        dept_u = (
            session.query(DepartmentUserDB)
            .filter(
                or_(
                    func.lower(DepartmentUserDB.azure_object_id) == uid_lower,
                    func.lower(DepartmentUserDB.user_email) == uid_lower,
                    func.lower(DepartmentUserDB.id) == uid_lower,
                )
            )
            .first()
        )
        if dept_u and dept_u.user_email:
            return dept_u.user_email
    except Exception:
        pass
    return f"{user_id}@company.com"


def _resolve_requester_name(requester_id: Optional[str], session: Session) -> str:
    """Resolve a raw Azure OID, profile ID, or email to a display name.

    Resolution order:
    1. Direct match by UserProfileDB.id (e.g. 'usr-emp-001').
    2. If requester_id looks like an email, query UserProfileDB directly by email.
    3. Otherwise treat it as an Azure OID GUID: look up DepartmentUserDB.azure_object_id
       to get the user's email, then resolve UserProfileDB by that email.
    4. Fall back to the email-prefix or the raw value if no profile exists.
    """
    if not requester_id:
        return "Employee User"

    try:
        from database.models_db import DepartmentUserDB, UserProfileDB

        # --- Case 1: direct profile ID match (e.g. usr-emp-001, usr-admin-dc3b56e9) ---
        prof = (
            session.query(UserProfileDB)
            .filter(func.lower(UserProfileDB.id) == requester_id.lower())
            .first()
        )
        if prof and prof.name:
            return prof.name

        # --- Case 2: direct OID match on user_profiles.azure_object_id ---
        prof2 = (
            session.query(UserProfileDB)
            .filter(func.lower(UserProfileDB.azure_object_id) == requester_id.lower())
            .first()
        )
        if prof2 and prof2.name:
            return prof2.name

        # --- Case 3: requester_id is already an email ---
        if "@" in requester_id:
            prof = (
                session.query(UserProfileDB)
                .filter(func.lower(UserProfileDB.email) == requester_id.lower())
                .first()
            )
            if prof and prof.name:
                return prof.name
            return requester_id.split("@")[0]

        # --- Case 3: requester_id is an Azure OID GUID ---
        # Step A: find the user's email from department_users
        dept_u = (
            session.query(DepartmentUserDB)
            .filter(
                func.lower(DepartmentUserDB.azure_object_id) == requester_id.lower()
            )
            .first()
        )
        if dept_u and dept_u.user_email:
            # Step B: resolve full name from user_profiles via email
            prof = (
                session.query(UserProfileDB)
                .filter(func.lower(UserProfileDB.email) == dept_u.user_email.lower())
                .first()
            )
            if prof and prof.name:
                return prof.name
            return dept_u.user_email.split("@")[0]

    except Exception:
        pass

    return requester_id


def _create_ticket_internal(ticket: TicketCreate, db: Optional[Session] = None) -> dict:
    session = db or SessionLocal()
    should_close = db is None

    try:
        now = datetime.now()
        now_str = now.isoformat()
        date_str = now.strftime("%Y-%m-%d")

        # Duplicate submission check within 5 seconds
        if ticket.title and ticket.description:
            cutoff = now - timedelta(seconds=5)
            recent_tickets = (
                session.query(TicketDB)
                .filter(
                    TicketDB.title == ticket.title,
                    TicketDB.description == ticket.description,
                )
                .all()
            )
            for rec in recent_tickets:
                if rec.createdAt:
                    try:
                        rec_time = datetime.fromisoformat(rec.createdAt)
                        if rec_time >= cutoff:
                            return rec.to_dict()
                    except Exception:
                        pass

        new_id = _generate_next_id(session)

        db_ticket = TicketDB(
            id=new_id,
            title=ticket.title,
            category=ticket.category or "IT Support",
            priority=ticket.priority or "Medium",
            status="Open",
            department=ticket.department or "IT",
            description=ticket.description,
            date=date_str,
            createdAt=now_str,
            is_anonymous=ticket.is_anonymous,
            attachment=ticket.attachment,
            requester_id=ticket.requester_id,
            assigned_to=getattr(ticket, "assigned_to", None),
            classification_status=(
                "Pending AI Triage"
                if getattr(ticket, "confidence", 0.0) == 0.0
                else "Classified"
            ),
            classification_confidence=str(getattr(ticket, "confidence", "")) or None,
            classification_reason=getattr(ticket, "reason", None),
            needs_human_review=getattr(ticket, "needs_human_review", False),
            model_deployment=(
                "mock"
                if os.getenv("USE_MOCK_AI", "false").lower() == "true"
                else os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5.2")
            ),
        )

        session.add(db_ticket)
        session.commit()
        session.refresh(db_ticket)
        result_dict = db_ticket.to_dict()

        # Trigger in-app notification & confirmation email
        try:
            if db_ticket.requester_id:
                create_notification(
                    title=f"Ticket Submitted - #{db_ticket.id}",
                    message=f"Your ticket '{db_ticket.title}' was submitted successfully.",
                    user_id=db_ticket.requester_id,
                    db=session,
                )
            recipient_email = _resolve_user_email(db_ticket.requester_id, session)
            if recipient_email:
                from services.email_service import send_ticket_created_email

                send_ticket_created_email(result_dict, recipient_email)
        except Exception as _notif_err:
            tracer.get_tracer("ticketgenie").start_span(
                "create_ticket_notification_error"
            )

        return result_dict
    finally:
        if should_close:
            session.close()


def get_all_tickets(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    search: Optional[str] = None,
    requester_id: Optional[str] = None,
    department: Optional[str] = None,
    assigned_to: Optional[str] = None,
    db: Optional[Session] = None,
) -> List[dict]:
    session = db or SessionLocal()
    should_close = db is None

    try:
        query = session.query(TicketDB)

        if requester_id:
            req_str = requester_id.lower().strip()
            target_ids = {req_str}
            try:
                from database.models_db import DepartmentUserDB, UserProfileDB

                dept_records = (
                    session.query(DepartmentUserDB)
                    .filter(
                        or_(
                            func.lower(DepartmentUserDB.user_email) == req_str,
                            func.lower(DepartmentUserDB.azure_object_id) == req_str,
                            func.lower(DepartmentUserDB.id) == req_str,
                        )
                    )
                    .all()
                )
                for rec in dept_records:
                    if rec.azure_object_id:
                        target_ids.add(rec.azure_object_id.lower())
                    if rec.user_email:
                        target_ids.add(rec.user_email.lower())
                    if rec.id:
                        target_ids.add(rec.id.lower())

                profiles = (
                    session.query(UserProfileDB)
                    .filter(
                        or_(
                            func.lower(UserProfileDB.id) == req_str,
                            func.lower(UserProfileDB.email) == req_str,
                        )
                    )
                    .all()
                )
                for prof in profiles:
                    if prof.id:
                        target_ids.add(prof.id.lower())
                    if prof.email:
                        target_ids.add(prof.email.lower())

            except Exception:
                pass

            query = query.filter(
                func.lower(TicketDB.requester_id).in_(list(target_ids))
            )

        if department and department.strip():
            dept_str = f"%{department.lower().strip()}%"
            query = query.filter(func.lower(TicketDB.department).like(dept_str))

        if assigned_to and assigned_to.strip():
            ass_str = assigned_to.lower().strip()
            if ass_str == "unassigned":
                query = query.filter(
                    or_(
                        TicketDB.assigned_to.is_(None),
                        func.lower(TicketDB.assigned_to) == "",
                    )
                )
            elif ass_str != "all":
                query = query.filter(
                    func.lower(TicketDB.assigned_to).like(f"%{ass_str}%")
                )

        if search:
            s = f"%{search.lower().strip()}%"
            query = query.filter(
                or_(
                    func.lower(TicketDB.title).like(s),
                    func.lower(TicketDB.id).like(s),
                    func.lower(TicketDB.category).like(s),
                    func.lower(TicketDB.description).like(s),
                    func.lower(TicketDB.assigned_to).like(s),
                )
            )

        if status and status.lower() != "all":
            query = query.filter(func.lower(TicketDB.status) == status.lower())

        if priority and priority.lower() != "all":
            query = query.filter(func.lower(TicketDB.priority) == priority.lower())

        results = query.all()
        res_list = []
        for t in results:
            d = t.to_dict()
            if t.is_anonymous:
                d["requester"] = "Anonymous Employee"
                d["requester_name"] = "Anonymous Employee"
            else:
                req_name = _resolve_requester_name(t.requester_id, session)
                d["requester"] = req_name
                d["requester_name"] = req_name
            res_list.append(d)
        return res_list
    finally:
        if should_close:
            session.close()


def get_ticket_by_id(ticket_id: str, db: Optional[Session] = None) -> Optional[dict]:
    session = db or SessionLocal()
    should_close = db is None

    try:
        ticket = (
            session.query(TicketDB)
            .filter(func.lower(TicketDB.id) == ticket_id.lower())
            .first()
        )
        if not ticket:
            return None
        d = ticket.to_dict()
        if ticket.is_anonymous:
            d["requester"] = "Anonymous Employee"
            d["requester_name"] = "Anonymous Employee"
        else:
            req_name = _resolve_requester_name(ticket.requester_id, session)
            d["requester"] = req_name
            d["requester_name"] = req_name
        return d
    finally:
        if should_close:
            session.close()


def update_ticket(
    ticket_id: str, ticket_update: TicketUpdate, db: Optional[Session] = None
) -> Optional[dict]:
    session = db or SessionLocal()
    should_close = db is None

    try:
        ticket = (
            session.query(TicketDB)
            .filter(func.lower(TicketDB.id) == ticket_id.lower())
            .first()
        )
        if ticket is None:
            return None

        tracked_fields = ("status", "priority", "category", "assigned_to")
        old_values = {field: getattr(ticket, field) for field in tracked_fields}
        update_data = ticket_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(ticket, field):
                if field == "assigned_to" and (value == "" or value is None):
                    setattr(ticket, field, None)
                elif value is not None:
                    setattr(ticket, field, value)

        ticket.updatedAt = datetime.now().isoformat()
        session.commit()
        session.refresh(ticket)
        result_dict = ticket.to_dict()
        new_status = ticket.status
        changed_fields = [
            field
            for field in tracked_fields
            if field in update_data and old_values[field] != getattr(ticket, field)
        ]

        # Notify the requester when a user-visible ticket field changes.
        old_status = old_values["status"]
        if ticket.requester_id and changed_fields:
            try:
                if "status" in changed_fields:
                    title = f"Ticket #{ticket.id} Status Updated"
                    message = (
                        f"Your ticket '{ticket.title}' status changed from "
                        f"'{old_status}' to '{new_status}'."
                    )
                else:
                    labels = {
                        "priority": "priority",
                        "category": "department",
                        "assigned_to": "assignee",
                    }
                    details = ", ".join(labels[field] for field in changed_fields)
                    title = f"Ticket #{ticket.id} Updated"
                    message = f"Your ticket '{ticket.title}' had its {details} updated."
                create_notification(title, message, ticket.requester_id, db=session)

                recipient_email = _resolve_user_email(ticket.requester_id, session)
                if recipient_email and "status" in changed_fields:
                    from services.email_service import send_ticket_status_updated_email

                    send_ticket_status_updated_email(
                        result_dict, old_status, new_status, recipient_email
                    )
            except Exception:
                pass

        return result_dict
    finally:
        if should_close:
            session.close()


# ---------------------------------------------------------------------------
# Ticket Comments CRUD
# ---------------------------------------------------------------------------


def add_ticket_comment(
    ticket_id: str,
    message: str,
    sender_id: str = "user",
    sender_role: str = "Employee",
    db: Optional[Session] = None,
) -> dict:
    session = db or SessionLocal()
    should_close = db is None

    try:
        import uuid

        from database.models_db import TicketCommentDB

        comment_id = f"cmt-{uuid.uuid4().hex[:8]}"
        now_str = datetime.now().isoformat()

        db_comment = TicketCommentDB(
            id=comment_id,
            ticket_id=ticket_id,
            sender_id=sender_id,
            sender_role=sender_role,
            message=message,
            createdAt=now_str,
        )

        session.add(db_comment)
        session.commit()
        session.refresh(db_comment)
        comment_dict = db_comment.to_dict()

        # Trigger notification & email
        try:
            ticket_obj = (
                session.query(TicketDB)
                .filter(func.lower(TicketDB.id) == ticket_id.lower())
                .first()
            )
            if ticket_obj and sender_role.lower() not in {"private", "system"}:
                ticket_dict = ticket_obj.to_dict()
                req_id = ticket_obj.requester_id

                if (
                    sender_id
                    and req_id
                    and sender_id.lower().strip() == req_id.lower().strip()
                ):
                    target_user = ticket_obj.assigned_to
                    target_email = _resolve_user_email(target_user, session)
                else:
                    target_user = req_id
                    target_email = _resolve_user_email(req_id, session)

                short_msg = message[:90] + "..." if len(message) > 90 else message
                if target_user:
                    create_notification(
                        title=f"New Comment on #{ticket_id}",
                        message=f'{sender_role} replied: "{short_msg}"',
                        user_id=target_user,
                        db=session,
                    )

                if target_email:
                    from services.email_service import send_ticket_comment_email

                    send_ticket_comment_email(ticket_dict, comment_dict, target_email)
        except Exception:
            pass

        return comment_dict
    finally:
        if should_close:
            session.close()


def get_ticket_comments(ticket_id: str, db: Optional[Session] = None) -> List[dict]:
    session = db or SessionLocal()
    should_close = db is None

    try:
        from database.models_db import TicketCommentDB

        comments = (
            session.query(TicketCommentDB)
            .filter(func.lower(TicketCommentDB.ticket_id) == ticket_id.lower())
            .order_by(TicketCommentDB.createdAt.asc())
            .all()
        )
        res_list = []
        for c in comments:
            d = c.to_dict()
            name = _resolve_requester_name(c.sender_id, session)
            d["sender_name"] = name
            if c.sender_id and ("-" in c.sender_id and len(c.sender_id) > 20):
                d["sender_id"] = name
            res_list.append(d)
        return res_list
    finally:
        if should_close:
            session.close()


# ---------------------------------------------------------------------------
# Department & Azure Object ID RBAC CRUD
# ---------------------------------------------------------------------------


def create_department(
    name: str,
    queue_name: str,
    description: Optional[str] = None,
    db: Optional[Session] = None,
) -> dict:
    session = db or SessionLocal()
    should_close = db is None

    try:
        import uuid

        from database.models_db import DepartmentDB

        existing = session.query(DepartmentDB).filter(DepartmentDB.name == name).first()
        if existing:
            return existing.to_dict()

        dept_id = f"dept-{uuid.uuid4().hex[:8]}"
        now_str = datetime.now().isoformat()

        dept = DepartmentDB(
            id=dept_id,
            name=name,
            queue_name=queue_name,
            description=description or f"Queue for {name}",
            createdAt=now_str,
        )
        session.add(dept)
        session.commit()
        session.refresh(dept)
        return dept.to_dict()
    finally:
        if should_close:
            session.close()


def list_departments(db: Optional[Session] = None) -> List[dict]:
    session = db or SessionLocal()
    should_close = db is None

    try:
        from database.models_db import DepartmentDB

        depts = session.query(DepartmentDB).all()
        if not depts:
            # Provide default initial departments if database is fresh
            defaults = [
                {"name": "IT Team", "queue_name": "IT - Service Desk"},
                {"name": "HR Team", "queue_name": "HR - Employee Relations"},
                {"name": "Accounting Team", "queue_name": "Accounting - Payroll"},
                {
                    "name": "Upper Executive Management",
                    "queue_name": "Upper Management - Leave Approval",
                },
                {
                    "name": "Workplace Operations Team",
                    "queue_name": "Workplace Operations - Facilities",
                },
            ]
            return defaults
        return [d.to_dict() for d in depts]
    finally:
        if should_close:
            session.close()


def add_department_user(
    department_name: str,
    azure_object_id: str,
    role: str = "Employee",
    user_email: Optional[str] = None,
    db: Optional[Session] = None,
) -> dict:
    session = db or SessionLocal()
    should_close = db is None

    try:
        import uuid

        from database.models_db import DepartmentUserDB

        user_id = f"uobj-{uuid.uuid4().hex[:8]}"
        now_str = datetime.now().isoformat()

        du = DepartmentUserDB(
            id=user_id,
            department_name=department_name,
            azure_object_id=azure_object_id,
            role=role,
            user_email=user_email,
            createdAt=now_str,
        )
        session.add(du)
        session.commit()
        session.refresh(du)
        return du.to_dict()
    finally:
        if should_close:
            session.close()


def remove_department_user(
    department_name: str, azure_object_id: str, db: Optional[Session] = None
) -> bool:
    session = db or SessionLocal()
    should_close = db is None

    try:
        from database.models_db import DepartmentUserDB

        record = (
            session.query(DepartmentUserDB)
            .filter(
                DepartmentUserDB.department_name == department_name,
                DepartmentUserDB.azure_object_id == azure_object_id,
            )
            .first()
        )
        if record:
            session.delete(record)
            session.commit()
            return True
        return False
    finally:
        if should_close:
            session.close()


def list_department_users(
    department_name: Optional[str] = None, db: Optional[Session] = None
) -> List[dict]:
    session = db or SessionLocal()
    should_close = db is None

    try:
        from database.models_db import DepartmentUserDB

        query = session.query(DepartmentUserDB)
        if department_name:
            query = query.filter(DepartmentUserDB.department_name == department_name)
        records = query.all()
        return [r.to_dict() for r in records]
    finally:
        if should_close:
            session.close()


# ---------------------------------------------------------------------------
# Leave Management & Analytics CRUD
# ---------------------------------------------------------------------------


def get_leave_tickets(db: Optional[Session] = None) -> List[dict]:
    session = db or SessionLocal()
    should_close = db is None

    try:
        leave_keywords = [
            "leave",
            "pto",
            "vacation",
            "medical",
            "parental",
            "bereavement",
            "sick",
        ]
        query = session.query(TicketDB)

        conditions = []
        for keyword in leave_keywords:
            pattern = f"%{keyword}%"
            conditions.extend(
                [
                    func.lower(TicketDB.category).like(pattern),
                    func.lower(TicketDB.title).like(pattern),
                    func.lower(TicketDB.description).like(pattern),
                ]
            )

        tickets = query.filter(or_(*conditions)).all()
        results = []
        for ticket in tickets:
            item = ticket.to_dict()
            item["requester"] = (
                "Anonymous Employee"
                if ticket.is_anonymous
                else _resolve_requester_name(ticket.requester_id, session)
            )
            results.append(item)
        return results
    finally:
        if should_close:
            session.close()


def get_analytics_summary(db: Optional[Session] = None) -> dict:
    session = db or SessionLocal()
    should_close = db is None

    try:
        all_tickets = session.query(TicketDB).all()
        total_count = len(all_tickets)
        resolved_count = sum(
            1 for t in all_tickets if (t.status or "").lower() == "resolved"
        )
        auto_resolved_count = sum(
            1 for t in all_tickets if getattr(t, "auto_resolved", False)
        )

        by_category = {}
        by_department = {}
        for t in all_tickets:
            cat = t.category or "Other"
            dept = t.department or "IT Team"
            by_category[cat] = by_category.get(cat, 0) + 1
            by_department[dept] = by_department.get(dept, 0) + 1

        auto_res_rate = (
            round((auto_resolved_count / total_count * 100), 1)
            if total_count > 0
            else 40.0
        )

        return {
            "total_tickets": total_count,
            "resolved_tickets": resolved_count,
            "auto_resolved_tickets": auto_resolved_count,
            "auto_resolution_rate_pct": auto_res_rate,
            "avg_resolution_time_hours": 3.4,
            "tickets_by_category": by_category,
            "tickets_by_department": by_department,
        }
    finally:
        if should_close:
            session.close()


# ---------------------------------------------------------------------------
# Announcements CRUD
# ---------------------------------------------------------------------------


def get_announcements(db: Optional[Session] = None) -> List[dict]:
    session = db or SessionLocal()
    should_close = db is None

    try:
        from database.models_db import AnnouncementDB

        records = (
            session.query(AnnouncementDB)
            .order_by(AnnouncementDB.createdAt.desc())
            .all()
        )
        if not records:
            # Seed standard announcements
            now_str = datetime.now().isoformat()
            defaults = [
                AnnouncementDB(
                    id="anc-1",
                    title="System Maintenance Notice",
                    content="Scheduled infrastructure maintenance on Saturday at 2 AM EST.",
                    category="System Alert",
                    author="IT Ops",
                    createdAt=now_str,
                ),
                AnnouncementDB(
                    id="anc-2",
                    title="New HR Policy Handbook Released",
                    content="Please review the updated employee handbook for 2026.",
                    category="HR Announcement",
                    author="HR Relations",
                    createdAt=now_str,
                ),
            ]
            for d in defaults:
                session.add(d)
            session.commit()
            records = (
                session.query(AnnouncementDB)
                .order_by(AnnouncementDB.createdAt.desc())
                .all()
            )

        return [r.to_dict() for r in records]
    finally:
        if should_close:
            session.close()


def create_announcement(
    title: str,
    content: str,
    category: str = "General Alert",
    author: str = "Admin Operations",
    db: Optional[Session] = None,
) -> dict:
    session = db or SessionLocal()
    should_close = db is None

    try:
        import uuid

        from database.models_db import AnnouncementDB

        anc_id = f"anc-{uuid.uuid4().hex[:8]}"
        now_str = datetime.now().isoformat()

        anc = AnnouncementDB(
            id=anc_id,
            title=title,
            content=content,
            category=category,
            author=author,
            createdAt=now_str,
        )
        session.add(anc)
        session.commit()
        session.refresh(anc)
        return anc.to_dict()
    finally:
        if should_close:
            session.close()


def delete_announcement(anc_id: str, db: Optional[Session] = None) -> bool:
    session = db or SessionLocal()
    should_close = db is None

    try:
        from database.models_db import AnnouncementDB

        anc = session.query(AnnouncementDB).filter(AnnouncementDB.id == anc_id).first()
        if anc:
            session.delete(anc)
            session.commit()
            return True
        return False
    finally:
        if should_close:
            session.close()


# ---------------------------------------------------------------------------
# Notifications CRUD
# ---------------------------------------------------------------------------


def get_notifications(user_ids: List[str], db: Optional[Session] = None) -> List[dict]:
    session = db or SessionLocal()
    should_close = db is None

    try:
        from database.models_db import NotificationDB

        target_ids = {
            str(user_id).lower().strip() for user_id in user_ids if str(user_id).strip()
        }
        if not target_ids:
            return []

        records = (
            session.query(NotificationDB)
            .filter(func.lower(NotificationDB.user_id).in_(list(target_ids)))
            .order_by(NotificationDB.createdAt.desc())
            .all()
        )

        return [r.to_dict() for r in records]
    finally:
        if should_close:
            session.close()


def create_notification(
    title: str, message: str, user_id: str, db: Optional[Session] = None
) -> dict:
    session = db or SessionLocal()
    should_close = db is None

    try:
        import uuid

        from database.models_db import NotificationDB

        notif_id = f"notif-{uuid.uuid4().hex[:8]}"
        now_str = datetime.now().isoformat()

        notif = NotificationDB(
            id=notif_id,
            user_id=user_id,
            title=title,
            message=message,
            is_read=False,
            createdAt=now_str,
        )
        session.add(notif)
        session.commit()
        session.refresh(notif)
        return notif.to_dict()
    finally:
        if should_close:
            session.close()


def mark_notification_read(
    notif_id: str, user_ids: List[str], db: Optional[Session] = None
) -> bool:
    session = db or SessionLocal()
    should_close = db is None

    try:
        from database.models_db import NotificationDB

        target_ids = {
            str(user_id).lower().strip() for user_id in user_ids if str(user_id).strip()
        }
        if not target_ids:
            return False
        notif = (
            session.query(NotificationDB)
            .filter(
                NotificationDB.id == notif_id,
                func.lower(NotificationDB.user_id).in_(list(target_ids)),
            )
            .first()
        )
        if notif:
            notif.is_read = True
            session.commit()
            return True
        return False
    finally:
        if should_close:
            session.close()


# ---------------------------------------------------------------------------
# Onboarding & Visas CRUD
# ---------------------------------------------------------------------------


def get_onboarding_records(db: Optional[Session] = None) -> List[dict]:
    session = db or SessionLocal()
    should_close = db is None

    try:
        from database.models_db import OnboardingDB

        records = (
            session.query(OnboardingDB).order_by(OnboardingDB.createdAt.desc()).all()
        )
        if not records:
            now_str = datetime.now().isoformat()
            defaults = [
                OnboardingDB(
                    id="onb-101",
                    employee_name="Aarav Sharma",
                    role="Senior Software Engineer",
                    department="IT Engineering",
                    visa_status="H-1B Active",
                    start_date="2026-09-01",
                    status="Completed",
                    createdAt=now_str,
                ),
                OnboardingDB(
                    id="onb-102",
                    employee_name="Elena Rostova",
                    role="Product Designer",
                    department="UX Design",
                    visa_status="OPT STEM",
                    start_date="2026-09-15",
                    status="In Progress",
                    createdAt=now_str,
                ),
                OnboardingDB(
                    id="onb-103",
                    employee_name="Marcus Vance",
                    role="Data Analyst",
                    department="HR Analytics",
                    visa_status="TN Visa",
                    start_date="2026-10-01",
                    status="Pending Documents",
                    createdAt=now_str,
                ),
            ]
            for d in defaults:
                session.add(d)
            session.commit()
            records = (
                session.query(OnboardingDB)
                .order_by(OnboardingDB.createdAt.desc())
                .all()
            )

        return [r.to_dict() for r in records]
    finally:
        if should_close:
            session.close()


def create_onboarding_record(
    employee_name: str,
    role: str,
    department: str,
    visa_status: str = "H1-B",
    start_date: str = "2026-09-01",
    status: str = "In Progress",
    db: Optional[Session] = None,
) -> dict:
    session = db or SessionLocal()
    should_close = db is None

    try:
        import uuid

        from database.models_db import OnboardingDB

        onb_id = f"onb-{uuid.uuid4().hex[:6]}"
        now_str = datetime.now().isoformat()

        rec = OnboardingDB(
            id=onb_id,
            employee_name=employee_name,
            role=role,
            department=department,
            visa_status=visa_status,
            start_date=start_date,
            status=status,
            createdAt=now_str,
        )
        session.add(rec)
        session.commit()
        session.refresh(rec)
        return rec.to_dict()
    finally:
        if should_close:
            session.close()


def update_onboarding_status(
    rec_id: str, new_status: str, db: Optional[Session] = None
) -> Optional[dict]:
    session = db or SessionLocal()
    should_close = db is None

    try:
        from database.models_db import OnboardingDB

        rec = session.query(OnboardingDB).filter(OnboardingDB.id == rec_id).first()
        if rec:
            rec.status = new_status
            session.commit()
            session.refresh(rec)
            return rec.to_dict()
        return None
    finally:
        if should_close:
            session.close()


# ---------------------------------------------------------------------------
# User Profile CRUD
# ---------------------------------------------------------------------------


def get_user_profile(
    user_id: Optional[str] = None,
    azure_oid: Optional[str] = None,
    email: Optional[str] = None,
    db: Optional[Session] = None,
) -> Optional[dict]:
    session = db or SessionLocal()
    should_close = db is None

    try:
        from sqlalchemy import func

        from database.models_db import UserProfileDB

        query = session.query(UserProfileDB)

        if user_id:
            user = query.filter(UserProfileDB.id == user_id).first()
            if user:
                return user.to_dict()

        if azure_oid:
            user = query.filter(
                func.lower(UserProfileDB.azure_object_id) == azure_oid.lower()
            ).first()
            if user:
                return user.to_dict()
            short_oid = azure_oid[:8]
            user = query.filter(UserProfileDB.id.like(f"%{short_oid}%")).first()
            if user:
                return user.to_dict()

        if email:
            user = query.filter(
                func.lower(UserProfileDB.email) == email.lower()
            ).first()
            if user:
                return user.to_dict()

        return None
    finally:
        if should_close:
            session.close()


def update_user_profile(
    user_id: Optional[str] = None,
    name: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    department: Optional[str] = None,
    role: Optional[str] = None,
    azure_object_id: Optional[str] = None,
    db: Optional[Session] = None,
) -> Optional[dict]:
    session = db or SessionLocal()
    should_close = db is None

    try:
        from database.models_db import UserProfileDB

        user = None
        if user_id:
            user = (
                session.query(UserProfileDB).filter(UserProfileDB.id == user_id).first()
            )
        if not user and azure_object_id:
            user = (
                session.query(UserProfileDB)
                .filter(
                    func.lower(UserProfileDB.azure_object_id) == azure_object_id.lower()
                )
                .first()
            )
        if not user and email:
            user = (
                session.query(UserProfileDB)
                .filter(func.lower(UserProfileDB.email) == email.lower())
                .first()
            )

        if not user:
            resolved_id = user_id
            if not resolved_id and azure_object_id:
                resolved_id = f"usr-admin-{azure_object_id[:8]}"
            if not resolved_id and email:
                resolved_id = f"usr-{email.split('@')[0].lower()}"
            user = UserProfileDB(
                id=resolved_id or "usr-unknown",
                name=name or "User",
                email=email or f"{resolved_id}@example.com",
                role=role or "Employee",
                department=department or "General",
            )
            session.add(user)

        if name:
            user.name = name
        if email:
            user.email = email
        if phone:
            user.phone = phone
        if department:
            user.department = department
        if role:
            user.role = role
        if azure_object_id:
            user.azure_object_id = azure_object_id

        session.commit()
        session.refresh(user)
        return user.to_dict()
    finally:
        if should_close:
            session.close()


def create_conversation(user_id: str, title: str, db: Optional[Session] = None) -> dict:
    session = db or SessionLocal()
    should_close = db is None

    try:
        import uuid

        from database.models_db import ChatConversationDB

        now_str = datetime.now().isoformat()
        conv = ChatConversationDB(
            id=f"chatconv-{uuid.uuid4().hex[:8]}",
            user_id=user_id,
            title=title,
            createdAt=now_str,
            updatedAt=now_str,
        )
        session.add(conv)
        session.commit()
        session.refresh(conv)
        return conv.to_dict()
    finally:
        if should_close:
            session.close()


def list_conversations(user_id: str, db: Optional[Session] = None) -> List[dict]:
    session = db or SessionLocal()
    should_close = db is None

    try:
        from database.models_db import ChatConversationDB

        records = (
            session.query(ChatConversationDB)
            .filter(func.lower(ChatConversationDB.user_id) == user_id.lower().strip())
            .order_by(ChatConversationDB.updatedAt.desc())
            .all()
        )
        return [r.to_dict() for r in records]
    finally:
        if should_close:
            session.close()


def get_conversation(
    conversation_id: str, user_id: str, db: Optional[Session] = None
) -> Optional[dict]:
    session = db or SessionLocal()
    should_close = db is None

    try:
        from database.models_db import ChatConversationDB

        record = (
            session.query(ChatConversationDB)
            .filter(
                ChatConversationDB.id == conversation_id,
                func.lower(ChatConversationDB.user_id) == user_id.lower().strip(),
            )
            .first()
        )
        return record.to_dict() if record else None
    finally:
        if should_close:
            session.close()


def get_conversation_messages(
    conversation_id: str, db: Optional[Session] = None
) -> List[dict]:
    session = db or SessionLocal()
    should_close = db is None

    try:
        from database.models_db import ChatMessageDB

        records = (
            session.query(ChatMessageDB)
            .filter(ChatMessageDB.conversation_id == conversation_id)
            .order_by(ChatMessageDB.createdAt.asc())
            .all()
        )
        return [r.to_dict() for r in records]
    finally:
        if should_close:
            session.close()


def add_conversation_message(
    conversation_id: str, role: str, content: str, db: Optional[Session] = None
) -> dict:
    session = db or SessionLocal()
    should_close = db is None

    try:
        import uuid

        from database.models_db import ChatConversationDB, ChatMessageDB

        now_str = datetime.now().isoformat()
        msg = ChatMessageDB(
            id=f"chatmsg-{uuid.uuid4().hex[:8]}",
            conversation_id=conversation_id,
            role=role,
            content=content,
            createdAt=now_str,
        )
        session.add(msg)

        conv = (
            session.query(ChatConversationDB)
            .filter(ChatConversationDB.id == conversation_id)
            .first()
        )
        if conv:
            conv.updatedAt = now_str

        session.commit()
        session.refresh(msg)
        return msg.to_dict()
    finally:
        if should_close:
            session.close()
