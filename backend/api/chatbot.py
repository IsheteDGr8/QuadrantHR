from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from database import crud
from database.connection import get_db
from models.chatbot import ChatAction, ChatIntent, ChatRequest, ChatResponse
from models.conversation import ConversationDetail, ConversationSummary, MessageOut
from services import conversation_service
from services.chatbot_service import handle_message
from services.jwt_verifier import verify_azure_user

router = APIRouter(prefix="/chatbot", tags=["chatbot"])


@router.post("/message", response_model=ChatResponse)
def chatbot_message(
    request: ChatRequest,
    current_user: dict = Depends(verify_azure_user),
    db: Session = Depends(get_db),
):
    owner_id = conversation_service.get_owner_id(current_user)

    if request.conversation_id and not crud.get_conversation(
        request.conversation_id, owner_id, db=db
    ):
        raise HTTPException(status_code=404, detail="Conversation not found")

    is_pdf_export_request = conversation_service.is_pdf_export_request(request.message)
    if is_pdf_export_request:
        if request.conversation_id:
            response = ChatResponse(
                message="I generated a PDF transcript of this conversation.",
                intent=ChatIntent.GENERAL,
                action=ChatAction(type="export_conversation_pdf"),
            )
        else:
            response = ChatResponse(
                message=(
                    "There is no saved conversation to export yet. Start a chat, "
                    "then ask me to generate its PDF transcript."
                ),
                intent=ChatIntent.GENERAL,
            )
    else:
        response = handle_message(request, current_user=current_user)

    if (
        request.message
        and request.message.strip()
        and not (is_pdf_export_request and not request.conversation_id)
    ):
        try:
            conversation = conversation_service.persist_turn(
                db,
                conversation_id=request.conversation_id,
                owner_id=owner_id,
                user_message=request.message,
                assistant_message=response.message,
            )
            response.conversation_id = conversation["id"]
        except conversation_service.ConversationNotFoundError as exc:
            raise HTTPException(
                status_code=404, detail="Conversation not found"
            ) from exc

    return response


@router.get("/conversations", response_model=List[ConversationSummary])
def list_conversations(
    current_user: dict = Depends(verify_azure_user),
    db: Session = Depends(get_db),
):
    owner_id = conversation_service.get_owner_id(current_user)
    records = crud.list_conversations(owner_id, db=db)
    return [
        ConversationSummary(
            id=r["id"],
            title=r["title"],
            created_at=r["createdAt"],
            updated_at=r["updatedAt"],
        )
        for r in records
    ]


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(
    conversation_id: str,
    current_user: dict = Depends(verify_azure_user),
    db: Session = Depends(get_db),
):
    owner_id = conversation_service.get_owner_id(current_user)
    conversation = crud.get_conversation(conversation_id, owner_id, db=db)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = crud.get_conversation_messages(conversation_id, db=db)
    return ConversationDetail(
        id=conversation["id"],
        title=conversation["title"],
        created_at=conversation["createdAt"],
        updated_at=conversation["updatedAt"],
        messages=[
            MessageOut(role=m["role"], content=m["content"], created_at=m["createdAt"])
            for m in messages
        ],
    )


@router.get("/conversations/{conversation_id}/export", response_class=Response)
def export_conversation_pdf(
    conversation_id: str,
    current_user: dict = Depends(verify_azure_user),
    db: Session = Depends(get_db),
):
    from services.document_service import generate_conversation_pdf

    owner_id = conversation_service.get_owner_id(current_user)
    conversation = crud.get_conversation(conversation_id, owner_id, db=db)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = crud.get_conversation_messages(conversation_id, db=db)
    pdf_bytes = generate_conversation_pdf(conversation, messages)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="genie_conversation_{conversation_id}.pdf"'
            )
        },
    )
