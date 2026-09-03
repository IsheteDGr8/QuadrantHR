from sqlalchemy import Boolean, Column, String, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class TicketDB(Base):
    __tablename__ = "tickets"

    id = Column(String(50), primary_key=True, index=True)
    title = Column(String(250), nullable=False)
    category = Column(String(100), nullable=False, default="IT Support")
    priority = Column(String(50), nullable=False, default="Medium")
    status = Column(String(50), nullable=False, default="Open")
    department = Column(String(100), nullable=True, default="IT Team")
    queue = Column(String(100), nullable=True, default="IT - Service Desk")
    description = Column(Text, nullable=False)
    date = Column(String(50), nullable=False)
    createdAt = Column(String(50), nullable=False)
    updatedAt = Column(String(50), nullable=True)
    is_anonymous = Column(Boolean, default=False, nullable=False)
    attachment = Column(Text, nullable=True)
    requester_id = Column(String(150), nullable=True, index=True)
    classification_status = Column(String(50), nullable=False, default="Classified")
    classification_confidence = Column(String(20), nullable=True)
    classification_reason = Column(Text, nullable=True)
    needs_human_review = Column(Boolean, default=False, nullable=False)
    model_deployment = Column(String(100), nullable=True)
    parent_ticket_id = Column(String(50), nullable=True)
    auto_resolved = Column(Boolean, default=False, nullable=False)
    is_synthetic = Column(Boolean, default=False, nullable=False, index=True)
    assigned_to = Column(String(150), nullable=True, index=True)
    onboarding_id = Column(String(50), nullable=True, index=True)
    due_date = Column(String(50), nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "category": self.category,
            "priority": self.priority,
            "status": self.status,
            "department": self.department or "IT Team",
            "queue": self.queue or "IT - Service Desk",
            "description": self.description,
            "date": self.date,
            "createdAt": self.createdAt,
            "updatedAt": self.updatedAt,
            "is_anonymous": self.is_anonymous,
            "attachment": self.attachment,
            "requester_id": self.requester_id,
            "assigned_to": self.assigned_to,
            "classification_status": self.classification_status,
            "classification_confidence": float(self.classification_confidence)
            if self.classification_confidence
            else None,
            "classification_reason": self.classification_reason,
            "needs_human_review": self.needs_human_review,
            "model_deployment": self.model_deployment,
            "parent_ticket_id": self.parent_ticket_id,
            "auto_resolved": self.auto_resolved,
            "is_synthetic": self.is_synthetic,
            "onboarding_id": self.onboarding_id,
            "due_date": self.due_date,
        }


class TicketCommentDB(Base):
    __tablename__ = "ticket_comments"

    id = Column(String(50), primary_key=True, index=True)
    ticket_id = Column(String(50), index=True, nullable=False)
    sender_id = Column(String(100), nullable=False, default="user")
    sender_role = Column(String(50), nullable=False, default="Employee")
    message = Column(Text, nullable=False)
    createdAt = Column(String(50), nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "ticket_id": self.ticket_id,
            "sender_id": self.sender_id,
            "sender_role": self.sender_role,
            "message": self.message,
            "createdAt": self.createdAt,
        }


class DepartmentDB(Base):
    __tablename__ = "departments"

    id = Column(String(50), primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    queue_name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    createdAt = Column(String(50), nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "queue_name": self.queue_name,
            "description": self.description,
            "createdAt": self.createdAt,
        }


class DepartmentUserDB(Base):
    __tablename__ = "department_users"

    id = Column(String(50), primary_key=True, index=True)
    department_name = Column(String(100), index=True, nullable=False)
    azure_object_id = Column(String(100), index=True, nullable=False)
    role = Column(String(50), nullable=False, default="Employee")
    user_email = Column(String(150), nullable=True)
    createdAt = Column(String(50), nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "department_name": self.department_name,
            "azure_object_id": self.azure_object_id,
            "role": self.role,
            "user_email": self.user_email,
            "createdAt": self.createdAt,
        }


class KnowledgeChunkDB(Base):
    __tablename__ = "knowledge_chunks"

    id = Column(String(50), primary_key=True, index=True)
    category = Column(String(100), nullable=False)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    source = Column(String(100), nullable=False, default="Ticketer Dynamic Ingestion")
    createdAt = Column(String(50), nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "category": self.category,
            "title": self.title,
            "content": self.content,
            "source": self.source,
            "createdAt": self.createdAt,
        }


class AnnouncementDB(Base):
    __tablename__ = "announcements"

    id = Column(String(50), primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    category = Column(String(100), nullable=False, default="General Alert")
    author = Column(String(100), nullable=False, default="Admin Operations")
    createdAt = Column(String(50), nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "category": self.category,
            "author": self.author,
            "createdAt": self.createdAt,
        }


class NotificationDB(Base):
    __tablename__ = "notifications"

    id = Column(String(50), primary_key=True, index=True)
    user_id = Column(String(100), nullable=False, default="user")
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)
    createdAt = Column(String(50), nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "message": self.message,
            "is_read": self.is_read,
            "createdAt": self.createdAt,
        }


class OnboardingDB(Base):
    __tablename__ = "onboarding"

    id = Column(String(50), primary_key=True, index=True)
    employee_name = Column(String(150), nullable=False)
    employee_email = Column(String(150), nullable=True)
    role = Column(String(100), nullable=False)
    department = Column(String(100), nullable=False)
    manager = Column(String(150), nullable=True)
    location = Column(String(150), nullable=True)
    visa_status = Column(String(100), nullable=False, default="H1-B / OPT")
    start_date = Column(String(50), nullable=False)
    status = Column(String(50), nullable=False, default="In Progress")
    createdAt = Column(String(50), nullable=False)
    created_by = Column(String(150), nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "employee_name": self.employee_name,
            "employee_email": self.employee_email,
            "role": self.role,
            "department": self.department,
            "manager": self.manager,
            "location": self.location,
            "visa_status": self.visa_status,
            "start_date": self.start_date,
            "status": self.status,
            "createdAt": self.createdAt,
            "created_by": self.created_by,
        }


class ChatConversationDB(Base):
    __tablename__ = "chat_conversations"

    id = Column(String(50), primary_key=True, index=True)
    user_id = Column(String(150), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    createdAt = Column(String(50), nullable=False)
    updatedAt = Column(String(50), nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "createdAt": self.createdAt,
            "updatedAt": self.updatedAt,
        }


class ChatMessageDB(Base):
    __tablename__ = "chat_messages"

    id = Column(String(50), primary_key=True, index=True)
    conversation_id = Column(String(50), nullable=False, index=True)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    createdAt = Column(String(50), nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "role": self.role,
            "content": self.content,
            "createdAt": self.createdAt,
        }


class UserProfileDB(Base):
    __tablename__ = "user_profiles"

    id = Column(String(50), primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    email = Column(String(150), nullable=False, unique=True)
    role = Column(String(100), nullable=False, default="Employee")
    department = Column(String(100), nullable=False, default="General")
    phone = Column(String(50), nullable=True, default="+1 (555) 019-2834")
    avatar = Column(String(50), nullable=True, default="NM")
    azure_object_id = Column(String(100), nullable=True, index=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "role": self.role,
            "department": self.department,
            "phone": self.phone,
            "avatar": self.avatar,
            "azure_object_id": self.azure_object_id,
        }
