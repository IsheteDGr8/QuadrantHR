from fastapi import Depends, FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from models import Policy, Ticket
from schemas import (
    IncidentRequest,
    IncidentResponse,
    TicketResponse,
    TicketSubmitRequest,
    TicketSubmitResponse,
)
from retrieval import find_matching_policy
from agent import IncidentAgent, AgentError

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Incident Report Assistant API",
    description="Backend + agent logic for incident intake: policy retrieval and follow-up question generation.",
    version="1.0.0",
)

agent = IncidentAgent()


# Contract requires HTTP 400 (not FastAPI's default 422) for a missing or
# unparseable request body on any endpoint — most relevantly incident_text.
@app.exception_handler(RequestValidationError)
async def validation_error_handler(request, exc: RequestValidationError):
    return JSONResponse(
        status_code=400,
        content={"detail": "Invalid request body.", "errors": exc.errors()},
    )


@app.get("/", tags=["Health"])
def home():
    return {"message": "Incident Report Assistant backend is working!"}


@app.post("/incident", response_model=IncidentResponse, tags=["Incidents"])
def submit_incident(request: IncidentRequest, db: Session = Depends(get_db)):
    incident_text = (request.incident_text or "").strip()

    if not incident_text:
        raise HTTPException(
            status_code=400,
            detail="incident_text is required and cannot be blank.",
        )

    matched_policy = find_matching_policy(db, incident_text)

    if matched_policy is None:
        ticket = Ticket(
            incident_summary=incident_text,
            status="no_match",
        )
        db.add(ticket)
        db.commit()
        db.refresh(ticket)

        return IncidentResponse(
            ticket_id=ticket.id,
            status=ticket.status,
            matched_policy_name=None,
            follow_up_question=None,
            error_message=None,
        )

    try:
        follow_up_question = agent.generate_follow_up_question(
            incident_text, matched_policy
        )
    except AgentError as exc:
        ticket = Ticket(
            incident_summary=incident_text,
            matched_policy_id=matched_policy.id,
            matched_policy_name=matched_policy.name,
            status="error",
            error_message=str(exc),
        )
        db.add(ticket)
        db.commit()
        db.refresh(ticket)

        return IncidentResponse(
            ticket_id=ticket.id,
            status=ticket.status,
            matched_policy_name=matched_policy.name,
            follow_up_question=None,
            error_message=ticket.error_message,
        )

    ticket = Ticket(
        incident_summary=incident_text,
        matched_policy_id=matched_policy.id,
        matched_policy_name=matched_policy.name,
        follow_up_question=follow_up_question,
        status="pending_review",
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    return IncidentResponse(
        ticket_id=ticket.id,
        status=ticket.status,
        matched_policy_name=matched_policy.name,
        follow_up_question=follow_up_question,
        error_message=None,
    )


@app.get("/ticket/{ticket_id}", response_model=TicketResponse, tags=["Tickets"])
def get_ticket(ticket_id: int, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()

    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found.")

    return ticket


@app.post(
    "/ticket/{ticket_id}/submit",
    response_model=TicketSubmitResponse,
    tags=["Tickets"],
)
def submit_ticket(
    ticket_id: int,
    request: TicketSubmitRequest,
    db: Session = Depends(get_db),
):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()

    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found.")

    if not request.confirmed:
        raise HTTPException(
            status_code=400,
            detail="confirmed must be true to submit a ticket.",
        )

    ticket.answer = request.answer
    ticket.status = "submitted"
    db.commit()

    return TicketSubmitResponse(status=ticket.status, ticket_id=ticket.id)
