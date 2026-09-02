from datetime import datetime, UTC

from models import FeedbackTicket, TicketStatus, TicketType
from storage_service import StorageService
from logger import get_logger

logger = get_logger(__name__)
storage = StorageService()


def _ticket_blob_path(org_id: str, ticket_id: str) -> str:
    return f"{org_id}/tickets/{ticket_id}.json"


def create_ticket(
    org_id: str,
    *,
    type: TicketType,
    title: str,
    body: str,
    created_by: str,
    role: str | None = None,
) -> FeedbackTicket:
    ticket = FeedbackTicket(
        type=type,
        role=role,
        title=title,
        body=body,
        created_by=created_by,
    )
    storage.save_json(_ticket_blob_path(org_id, ticket.id), ticket.model_dump())
    logger.info(f"Ticket {ticket.id} ({type.value}) created for org {org_id} by {created_by}")
    return ticket


def list_tickets(org_id: str) -> list[FeedbackTicket]:
    prefix = f"{org_id}/tickets/"
    tickets = []
    for name in storage.list_blobs(prefix=prefix):
        data = storage.load_json(name)
        if data:
            tickets.append(FeedbackTicket(**data))
    return sorted(tickets, key=lambda t: t.created_at, reverse=True)


def resolve_ticket(org_id: str, ticket_id: str) -> FeedbackTicket | None:
    path = _ticket_blob_path(org_id, ticket_id)
    data = storage.load_json(path)
    if not data:
        return None

    ticket = FeedbackTicket(**data)
    ticket.status = TicketStatus.resolved
    ticket.resolved_at = datetime.now(UTC)
    storage.save_json(path, ticket.model_dump())
    logger.info(f"Ticket {ticket_id} resolved for org {org_id}")
    return ticket
