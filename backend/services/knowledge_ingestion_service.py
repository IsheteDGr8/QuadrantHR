"""Secure document ingestion for the TicketGenie corporate knowledge base."""

from __future__ import annotations

import hashlib
import io
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote

from fastapi import HTTPException, UploadFile, status

from services.embedding_service import embedding_service

CONTAINER_NAME = os.getenv("KNOWLEDGE_BLOB_CONTAINER", "ticket-genie-knowledge")
INDEX_NAME = os.getenv("AISEARCH_INDEX_NAME", "group-1")
MAX_FILE_BYTES = int(os.getenv("KNOWLEDGE_MAX_FILE_BYTES", str(15 * 1024 * 1024)))
ALLOWED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx"}
ALLOWED_CATEGORIES = {
    "General",
    "HR",
    "IT",
    "Accounting",
    "WorkplaceOperations",
}


def _has_azure_identity_configuration() -> bool:
    """Whether DefaultAzureCredential has a configured non-interactive identity."""
    has_managed_identity = bool(
        os.getenv("IDENTITY_ENDPOINT") or os.getenv("MSI_ENDPOINT")
    )
    has_service_principal = all(
        os.getenv(name)
        for name in ("AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET")
    )
    return has_managed_identity or has_service_principal


def require_knowledge_manager(current_user: dict) -> dict:
    """Allow current policy-management roles from verified identity; fail closed."""
    role = str(current_user.get("role") or "").strip().casefold()
    if role not in {"admin", "super admin", "ticketer"} and not current_user.get(
        "is_dev", False
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Knowledge base management requires Admin or Ticketer access.",
        )
    return current_user


def _blob_container():
    from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
    from azure.storage.blob import BlobServiceClient

    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "").strip()
    if connection_string:
        service = BlobServiceClient.from_connection_string(connection_string)
    else:
        account_name = os.getenv("AZURE_STORAGE_ACCOUNT_NAME", "").strip()
        account_key = os.getenv("AZURE_STORAGE_ACCOUNT_KEY", "").strip()
        if not account_name:
            raise RuntimeError("Azure knowledge storage is not configured.")
        if account_key:
            credential: Any = account_key
        elif os.getenv("IDENTITY_ENDPOINT") or os.getenv("MSI_ENDPOINT"):
            # Production's system-assigned Web App identity owns the Blob
            # data-plane role in Terraform. Select it explicitly so unrelated
            # AZURE_CLIENT_* settings cannot take precedence.
            credential = ManagedIdentityCredential()
        elif _has_azure_identity_configuration():
            credential = DefaultAzureCredential(
                exclude_managed_identity_credential=True
            )
        else:
            raise RuntimeError(
                "Knowledge storage requires a connection string, account key, "
                "managed identity, or Azure service-principal credentials."
            )
        service = BlobServiceClient(
            account_url=f"https://{account_name}.blob.core.windows.net",
            credential=credential,
        )
    return service.get_container_client(CONTAINER_NAME)


def _search_client():
    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents import SearchClient

    endpoint = os.getenv("AISEARCH_ENDPOINT", "").strip()
    api_key = os.getenv("AISEARCH_APIKEY", "").strip()
    if not endpoint or not api_key:
        raise RuntimeError("Azure AI Search is not configured.")
    return SearchClient(endpoint, INDEX_NAME, AzureKeyCredential(api_key))


def _extract_text(data: bytes, extension: str) -> str:
    if extension in {".txt", ".md"}:
        return data.decode("utf-8-sig")
    if extension == ".pdf":
        from pypdf import PdfReader

        return "\n\n".join(
            page.extract_text() or "" for page in PdfReader(io.BytesIO(data))
        )
    if extension == ".docx":
        from docx import Document

        doc = Document(io.BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    raise ValueError("Unsupported document type.")


def _chunks(text: str, target_chars: int = 3500, overlap_chars: int = 400) -> list[str]:
    normalized = re.sub(r"[ \t]+", " ", text).strip()
    if not normalized:
        return []
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", normalized) if p.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(current) + len(paragraph) + 2 <= target_chars:
            current = f"{current}\n\n{paragraph}".strip()
            continue
        if current:
            chunks.append(current)
        while len(paragraph) > target_chars:
            chunks.append(paragraph[:target_chars])
            paragraph = paragraph[target_chars - overlap_chars :]
        current = paragraph
    if current:
        chunks.append(current)
    return chunks


async def ingest_document(
    upload: UploadFile,
    *,
    title: str,
    category: str,
    uploaded_by: dict,
) -> dict:
    if category not in ALLOWED_CATEGORIES:
        raise HTTPException(status_code=422, detail="Invalid knowledge category.")
    original_name = Path(upload.filename or "").name
    extension = Path(original_name).suffix.casefold()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415, detail="Upload a PDF, DOCX, TXT, or Markdown file."
        )
    data = await upload.read(MAX_FILE_BYTES + 1)
    if not data or len(data) > MAX_FILE_BYTES:
        raise HTTPException(
            status_code=413, detail="Document is empty or exceeds the 15 MB limit."
        )
    try:
        text = _extract_text(data, extension)
    except Exception as exc:
        raise HTTPException(
            status_code=422, detail="The document text could not be extracted."
        ) from exc
    parts = _chunks(text)
    if not parts:
        raise HTTPException(
            status_code=422, detail="The document contains no extractable text."
        )

    digest = hashlib.sha256(data).hexdigest()
    container = _blob_container()
    for existing in container.list_blobs(
        name_starts_with="managed/", include=["metadata"]
    ):
        existing_metadata = existing.metadata or {}
        if existing_metadata.get("sha256") == digest:
            return {
                "id": existing_metadata.get("document_id"),
                "title": unquote(existing_metadata.get("title") or "") or title,
                "filename": Path(existing.name).name,
                "category": existing_metadata.get("category"),
                "size_bytes": existing.size,
                "chunk_count": None,
                "uploaded_at": existing_metadata.get("uploaded_at"),
                "uploaded_by": existing_metadata.get("uploaded_by_oid"),
                "status": "already_indexed",
            }

    document_id = str(uuid.uuid4())
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", original_name).strip("-")
    blob_path = f"managed/{document_id}/{safe_name}"
    now = datetime.now(timezone.utc).isoformat()
    metadata = {
        "document_id": document_id,
        "title": quote(title[:255], safe=""),
        "category": category,
        "uploaded_by_oid": str(uploaded_by["oid"])[:128],
        "uploaded_at": now,
        "sha256": digest,
    }
    container.upload_blob(blob_path, data, overwrite=False, metadata=metadata)
    try:
        vectors = embedding_service.embed_batch(parts)
        search_docs = [
            {
                "id": f"{document_id}-{index:04d}",
                "parent_id": document_id,
                "content": chunk,
                "contentVector": vector,
                "category": category,
                "source": title,
            }
            for index, (chunk, vector) in enumerate(zip(parts, vectors, strict=True))
        ]
        results = _search_client().upload_documents(search_docs)
        if not all(result.succeeded for result in results):
            raise RuntimeError("One or more search chunks failed to index.")
    except Exception:
        container.delete_blob(blob_path)
        raise

    try:
        from services.prompt_cache_service import prompt_cache

        prompt_cache.purge()
    except Exception:
        pass

    return {
        "id": document_id,
        "title": title,
        "filename": original_name,
        "category": category,
        "size_bytes": len(data),
        "chunk_count": len(parts),
        "uploaded_at": now,
        "uploaded_by": uploaded_by.get("email"),
        "status": "indexed",
    }


def list_documents() -> list[dict]:
    documents = []
    for blob in _blob_container().list_blobs(include=["metadata"]):
        metadata = blob.metadata or {}
        documents.append(
            {
                "id": metadata.get("document_id") or blob.name,
                "title": unquote(metadata.get("title") or "") or Path(blob.name).name,
                "filename": Path(blob.name).name,
                "category": metadata.get("category"),
                "size_bytes": blob.size,
                "uploaded_at": metadata.get("uploaded_at")
                or (blob.last_modified.isoformat() if blob.last_modified else None),
                "uploaded_by": metadata.get("uploaded_by_oid"),
                "status": "indexed" if metadata.get("document_id") else "legacy",
            }
        )
    return sorted(
        documents, key=lambda item: item.get("uploaded_at") or "", reverse=True
    )
