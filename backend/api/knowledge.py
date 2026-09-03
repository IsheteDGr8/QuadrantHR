"""Role-protected knowledge document management API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from services.jwt_verifier import verify_azure_user
from services.knowledge_ingestion_service import (
    ALLOWED_CATEGORIES,
    ingest_document,
    list_documents,
    require_knowledge_manager,
)

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.post("/documents", status_code=201)
async def upload_knowledge_document(
    title: str = Form(..., min_length=3, max_length=255),
    category: str = Form(...),
    file: UploadFile = File(...),
    current_user: dict = Depends(verify_azure_user),
):
    require_knowledge_manager(current_user)
    try:
        return await ingest_document(
            file, title=title.strip(), category=category, uploaded_by=current_user
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail="Knowledge indexing is unavailable."
        ) from exc


@router.get("/documents")
def get_knowledge_documents(
    current_user: dict = Depends(verify_azure_user),
):
    require_knowledge_manager(current_user)
    try:
        return {"documents": list_documents(), "categories": sorted(ALLOWED_CATEGORIES)}
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail="Knowledge storage is unavailable."
        ) from exc
