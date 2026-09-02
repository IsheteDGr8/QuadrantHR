from datetime import datetime

from pydantic import BaseModel, field_validator


# --------------------------------------------------
# POST /incident
# --------------------------------------------------

# incident_text is optional/untyped-permissive here on purpose: a pydantic
# ValidationError (missing field, wrong type) becomes an HTTP 422, but the
# contract requires HTTP 400 for an empty/invalid incident_text. Letting
# this field accept None means pydantic never 422s on it — the actual
# blank/missing check happens explicitly in the endpoint (see main.py) so
# the status code is exactly what Person B's UI expects either way.
class IncidentRequest(BaseModel):
    incident_text: str | None = None


class IncidentResponse(BaseModel):
    ticket_id: int
    status: str
    matched_policy_name: str | None = None
    follow_up_question: str | None = None
    error_message: str | None = None


# --------------------------------------------------
# GET /ticket/:id
# --------------------------------------------------

class TicketResponse(BaseModel):
    id: int
    incident_summary: str
    matched_policy_id: int | None
    matched_policy_name: str | None
    follow_up_question: str | None
    answer: str | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --------------------------------------------------
# POST /ticket/:id/submit
# --------------------------------------------------

class TicketSubmitRequest(BaseModel):
    answer: str
    confirmed: bool

    @field_validator("answer")
    @classmethod
    def validate_not_blank(cls, value: str):
        value = value.strip()

        if not value:
            raise ValueError("answer cannot be blank.")

        return value


class TicketSubmitResponse(BaseModel):
    status: str
    ticket_id: int
