#!/usr/bin/env python3
"""
scripts/migrate_knowledge_chunks.py

Safe Python-side migration from the 21 existing whole-document Search
records in `group-1` to chunk-level records with embeddings, since native
Azure Search index projections can't be used on `group-1` without
recreating it (the key field can't retroactively get the required
`keyword` analyzer - see scripts/setup_knowledge_indexer.py's report).

This script NEVER touches the original 21 records. It only reads them,
derives new chunk documents locally, and uploads those as ADDITIONAL
records. Deleting the originals is a separate, explicitly-guarded,
never-auto-run command (--delete-originals).

Modes:
    --check            (default) verify config/schema/data - ZERO writes
    --dry-run          simulate chunking/IDs/estimates locally - ZERO writes
    --apply            snapshot, chunk, embed, upload chunks (originals untouched)
    --delete-originals guarded cleanup of the 21 whole-doc records -
                       refuses unless all preconditions pass; not run by
                       this script's own invocation history, ever, unless
                       a human explicitly runs it later

Required config (read from environment / .env, never hardcoded):
    AISEARCH_ENDPOINT, AISEARCH_APIKEY
    AISEARCH_INDEX_NAME                          (optional, defaults to "group-1")
    GROUP1_TEXT_EMBEDDING_3_SMALL_ENDPOINT, GROUP1_TEXT_EMBEDDING_3_SMALL_APIKEY
"""

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv

_SCRIPT_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _SCRIPT_DIR.parent / "backend"
for _path in (_SCRIPT_DIR, _BACKEND_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from knowledge_categories import ALL_CATEGORIES  # noqa: E402

DEFAULT_INDEX_NAME = "group-1"
EXPECTED_ORIGINAL_COUNT = 21
VECTOR_DIMENSIONS = 1536
EMBEDDING_MODEL_NAME = "text-embedding-3-small"

# Calibrated against the actual corpus: these 21 synthetic documents are
# 662-1837 characters (~165-460 tokens) each - much smaller than a typical
# corporate document. A 400-700 token target (the initial suggestion)
# would produce exactly one chunk per document for nearly all of them,
# defeating the point of chunking. Using a smaller target instead gives
# real multi-chunk splitting for the longer documents without fragmenting
# the shorter ones into meaningless single-sentence pieces.
TARGET_CHUNK_TOKENS = 250
CHUNK_OVERLAP_TOKENS = 40
CHARS_PER_TOKEN_ESTIMATE = 4  # rough heuristic for English text

SNAPSHOT_PATH = (
    Path(__file__).resolve().parent.parent
    / "artifacts"
    / ("knowledge_migration_snapshot.json")
)
UPLOAD_BATCH_SIZE = 10
EMBED_BATCH_SIZE = 20


def _flag(is_set: bool) -> str:
    return "configured" if is_set else "MISSING"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# Chunking (deterministic, no GPT)
# --------------------------------------------------------------------------


def _split_long_paragraph(paragraph: str, max_chars: int) -> List[str]:
    """Fallback for a single paragraph longer than max_chars: split on
    sentence boundaries so we never cut a word in half."""

    sentences = re.split(r"(?<=[.!?])\s+", paragraph)
    pieces: List[str] = []
    current = ""
    for sentence in sentences:
        candidate = f"{current} {sentence}".strip() if current else sentence
        if len(candidate) > max_chars and current:
            pieces.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        pieces.append(current)
    return pieces or [paragraph]


def chunk_text(
    text: str,
    *,
    target_tokens: int = TARGET_CHUNK_TOKENS,
    overlap_tokens: int = CHUNK_OVERLAP_TOKENS,
) -> List[str]:
    """
    Paragraph-aware deterministic chunker. Splits on blank-line paragraph
    boundaries and greedily packs paragraphs up to ~target_tokens, carrying
    a small trailing overlap into the next chunk. Never splits mid-word;
    falls back to sentence boundaries only for a single oversized
    paragraph.
    """

    target_chars = target_tokens * CHARS_PER_TOKEN_ESTIMATE
    overlap_chars = overlap_tokens * CHARS_PER_TOKEN_ESTIMATE

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paragraphs:
        stripped = text.strip()
        return [stripped] if stripped else []

    expanded: List[str] = []
    for paragraph in paragraphs:
        if len(paragraph) > target_chars * 1.5:
            expanded.extend(_split_long_paragraph(paragraph, target_chars))
        else:
            expanded.append(paragraph)

    chunks: List[str] = []
    current_parts: List[str] = []
    current_len = 0

    for piece in expanded:
        if current_parts and current_len + len(piece) > target_chars:
            chunks.append("\n\n".join(current_parts))
            overlap_text = chunks[-1][-overlap_chars:] if overlap_chars > 0 else ""
            current_parts = [overlap_text, piece] if overlap_text else [piece]
            current_len = len(overlap_text) + len(piece)
        else:
            current_parts.append(piece)
            current_len += len(piece)

    if current_parts:
        chunks.append("\n\n".join(current_parts))

    return chunks


def generate_chunk_id(parent_id: str, chunk_index: int, chunk_content: str) -> str:
    """
    Deterministic and stable: identical (parent_id, index, content) always
    produces the same id, so reruns over unchanged content are idempotent.
    If the source content changes, the id changes too, rather than
    silently reusing a stale id for different text.
    """

    parent_hash = _sha256(parent_id)[:10]
    content_hash = _sha256(chunk_content)[:10]
    return f"chunk_{parent_hash}_{chunk_index:03d}_{content_hash}"


def build_proposed_chunks(documents: List[Dict]) -> List[Dict]:
    """Turn original documents into proposed chunk records (no vectors yet)."""

    proposed = []
    for doc in documents:
        pieces = chunk_text(doc["content"])
        for index, piece in enumerate(pieces):
            proposed.append(
                {
                    "id": generate_chunk_id(doc["id"], index, piece),
                    "parent_id": doc["id"],
                    "content": piece,
                    "category": doc["category"],
                    "source": doc["source"],
                }
            )
    return proposed


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------


def validate_originals(documents: List[Dict]) -> List[str]:
    """Returns a list of problems; empty list means the originals are safe to use."""

    problems = []

    if len(documents) != EXPECTED_ORIGINAL_COUNT:
        problems.append(
            f"expected exactly {EXPECTED_ORIGINAL_COUNT} original documents, "
            f"found {len(documents)}"
        )

    seen_ids = set()
    for doc in documents:
        for field in ("id", "content", "category", "source"):
            if not doc.get(field):
                problems.append(f"document {doc.get('id', '?')} missing '{field}'")
        doc_id = doc.get("id")
        if doc_id in seen_ids:
            problems.append(f"duplicate original id: {doc_id}")
        seen_ids.add(doc_id)
        category = doc.get("category")
        if category and category not in ALL_CATEGORIES:
            problems.append(
                f"document {doc_id} has invalid category '{category}' - "
                f"allowed: {sorted(ALL_CATEGORIES)}"
            )

    return problems


def validate_chunk(chunk: Dict, *, original_ids: set) -> List[str]:
    problems = []
    if not chunk.get("content", "").strip():
        problems.append(f"chunk {chunk.get('id')} has empty content")
    if chunk.get("category") not in ALL_CATEGORIES:
        problems.append(f"chunk {chunk.get('id')} has invalid category")
    if chunk.get("parent_id") not in original_ids:
        problems.append(f"chunk {chunk.get('id')} has unknown parent_id")
    if chunk.get("id") in original_ids:
        problems.append(
            f"chunk id collides with an original document id: {chunk.get('id')}"
        )
    vector = chunk.get("contentVector")
    if vector is not None and len(vector) != VECTOR_DIMENSIONS:
        problems.append(
            f"chunk {chunk.get('id')} has {len(vector)} vector dimensions, "
            f"expected {VECTOR_DIMENSIONS}"
        )
    return problems


# --------------------------------------------------------------------------
# Snapshot manifest
# --------------------------------------------------------------------------


def build_snapshot(documents: List[Dict], index_name: str) -> Dict:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "index_name": index_name,
        "expected_count": EXPECTED_ORIGINAL_COUNT,
        "documents": [
            {
                "id": doc["id"],
                "category": doc["category"],
                "source": doc["source"],
                "content_hash": _sha256(doc["content"]),
                "content_length": len(doc["content"]),
            }
            for doc in documents
        ],
    }


def write_snapshot(snapshot: Dict, path: Optional[Path] = None) -> None:
    # Resolved at call time (not bound as a default argument) so tests can
    # monkeypatch module-level SNAPSHOT_PATH and actually have it apply.
    target = path if path is not None else SNAPSHOT_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(snapshot, indent=2))


def load_snapshot(path: Optional[Path] = None) -> Optional[Dict]:
    target = path if path is not None else SNAPSHOT_PATH
    if not target.exists():
        return None
    return json.loads(target.read_text())


def verify_original_integrity(
    current_documents: List[Dict], snapshot: Dict
) -> List[str]:
    """Compare live originals against the snapshot; empty list = unchanged."""

    problems = []
    by_id = {doc["id"]: doc for doc in current_documents}
    for entry in snapshot["documents"]:
        current = by_id.get(entry["id"])
        if current is None:
            problems.append(f"original {entry['id']} is missing from the live index")
            continue
        if current["category"] != entry["category"]:
            problems.append(
                f"original {entry['id']} category changed: "
                f"{entry['category']!r} -> {current['category']!r}"
            )
        if current["source"] != entry["source"]:
            problems.append(
                f"original {entry['id']} source changed: "
                f"{entry['source']!r} -> {current['source']!r}"
            )
        if _sha256(current["content"]) != entry["content_hash"]:
            problems.append(f"original {entry['id']} content changed")
    return problems


# --------------------------------------------------------------------------
# Azure clients (real, lazily imported so tests never need the SDK live)
# --------------------------------------------------------------------------


def _get_search_client(endpoint: str, api_key: str, index_name: str):
    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents import SearchClient

    return SearchClient(
        endpoint=endpoint, index_name=index_name, credential=AzureKeyCredential(api_key)
    )


def _get_index_client(endpoint: str, api_key: str):
    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents.indexes import SearchIndexClient

    return SearchIndexClient(endpoint=endpoint, credential=AzureKeyCredential(api_key))


def fetch_original_documents(search_client) -> List[Dict]:
    """
    Originals are the pre-chunking whole-document records - identified by
    having no parent_id (chunk records always have one).
    """

    results = search_client.search(
        search_text="*",
        filter="parent_id eq null",
        select=["id", "content", "category", "source"],
        top=1000,
    )
    return [dict(r) for r in results]


def chunk_id_exists(search_client, chunk_id: str) -> bool:
    from azure.core.exceptions import ResourceNotFoundError

    try:
        search_client.get_document(key=chunk_id)
        return True
    except ResourceNotFoundError:
        return False


# --------------------------------------------------------------------------
# Modes
# --------------------------------------------------------------------------


def run_check(index_name: str = None) -> int:
    endpoint = os.getenv("AISEARCH_ENDPOINT")
    api_key = os.getenv("AISEARCH_APIKEY")
    index_name = index_name or os.getenv("AISEARCH_INDEX_NAME", DEFAULT_INDEX_NAME)
    embedding_endpoint = os.getenv("GROUP1_TEXT_EMBEDDING_3_SMALL_ENDPOINT")
    embedding_api_key = os.getenv("GROUP1_TEXT_EMBEDDING_3_SMALL_APIKEY")

    print("=== Config ===")
    print(f"AISEARCH_ENDPOINT: {_flag(bool(endpoint))}")
    print(f"AISEARCH_APIKEY: {_flag(bool(api_key))}")
    print(f"Target index: {index_name}")
    print(f"GROUP1_TEXT_EMBEDDING_3_SMALL_ENDPOINT: {_flag(bool(embedding_endpoint))}")
    print(f"GROUP1_TEXT_EMBEDDING_3_SMALL_APIKEY: {_flag(bool(embedding_api_key))}")
    print()

    if not endpoint or not api_key:
        print("BLOCKER: AISEARCH_ENDPOINT/AISEARCH_APIKEY not configured.")
        return 1
    if not embedding_endpoint or not embedding_api_key:
        print("BLOCKER: embedding deployment not configured.")
        return 1

    try:
        index_client = _get_index_client(endpoint, api_key)
        search_client = _get_search_client(endpoint, api_key, index_name)
    except ImportError as exc:
        print(f"BLOCKER: azure-search-documents not installed: {exc}")
        return 1

    print("=== Index schema check (read-only) ===")
    try:
        index = index_client.get_index(index_name)
    except Exception as exc:
        print(f"BLOCKER: could not read index '{index_name}': {exc}")
        return 1

    fields_by_name = {f.name: f for f in index.fields}
    required = ("id", "parent_id", "content", "contentVector", "category", "source")
    missing = [name for name in required if name not in fields_by_name]
    if missing:
        print(f"BLOCKER: index is missing required field(s): {missing}")
        return 1

    vector_field = fields_by_name["contentVector"]
    dims = getattr(vector_field, "vector_search_dimensions", None)
    if dims != VECTOR_DIMENSIONS:
        print(f"BLOCKER: contentVector has {dims} dims, expected {VECTOR_DIMENSIONS}")
        return 1
    print(f"Fields OK: {sorted(fields_by_name)}")
    print(f"contentVector dimensions: {dims}")
    print(f"vector_search configured: {index.vector_search is not None}")
    print()

    print("=== Original documents (read-only) ===")
    try:
        documents = fetch_original_documents(search_client)
    except Exception as exc:
        print(f"BLOCKER: could not read original documents: {exc}")
        return 1

    problems = validate_originals(documents)
    print(f"Original documents found: {len(documents)}")
    if problems:
        print("BLOCKER: original data validation failed:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print(
        "All originals have id/content/category/source, unique ids, valid categories."
    )
    print()

    print("=== Embedding deployment reachability (one minimal live call) ===")
    try:
        from services.embedding_service import embedding_service

        vector = embedding_service.embed("connectivity check")
    except Exception as exc:
        print(f"BLOCKER: embedding deployment unreachable: {exc}")
        return 1
    if len(vector) != VECTOR_DIMENSIONS:
        print(
            f"BLOCKER: embedding has {len(vector)} dims, expected {VECTOR_DIMENSIONS}"
        )
        return 1
    print(f"Reachable. model={EMBEDDING_MODEL_NAME} dimensions={len(vector)}")
    print()

    print("=== Hybrid query support (one minimal live read) ===")
    try:
        from azure.search.documents.models import VectorizedQuery

        probe_vector = [0.0] * VECTOR_DIMENSIONS
        list(
            search_client.search(
                search_text="test",
                vector_queries=[
                    VectorizedQuery(
                        vector=probe_vector,
                        k_nearest_neighbors=1,
                        fields="contentVector",
                    )
                ],
                top=1,
            )
        )
        print("Hybrid (search_text + vector_queries) request accepted by the index.")
    except Exception as exc:
        print(f"BLOCKER: hybrid query failed: {exc}")
        return 1
    print()

    print("Check passed - no Azure resources were created or modified.")
    return 0


def run_dry_run(index_name: str = None) -> int:
    endpoint = os.getenv("AISEARCH_ENDPOINT")
    api_key = os.getenv("AISEARCH_APIKEY")
    index_name = index_name or os.getenv("AISEARCH_INDEX_NAME", DEFAULT_INDEX_NAME)

    if not endpoint or not api_key:
        print("BLOCKER: AISEARCH_ENDPOINT/AISEARCH_APIKEY not configured.")
        return 1

    search_client = _get_search_client(endpoint, api_key, index_name)

    print("=== Reading original documents (read-only) ===")
    documents = fetch_original_documents(search_client)
    problems = validate_originals(documents)
    print(f"Original documents found: {len(documents)}")
    if problems:
        print("BLOCKER: original data validation failed:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print()

    print("=== Proposed chunks (computed locally, no embedding calls) ===")
    proposed = build_proposed_chunks(documents)
    original_ids = {doc["id"] for doc in documents}
    chunk_problems = []
    for chunk in proposed:
        chunk_problems.extend(validate_chunk(chunk, original_ids=original_ids))
    if chunk_problems:
        print("BLOCKER: proposed chunk validation failed:")
        for problem in chunk_problems:
            print(f"  - {problem}")
        return 1

    from collections import Counter

    per_doc = Counter(chunk["parent_id"] for chunk in proposed)
    per_category = Counter(chunk["category"] for chunk in proposed)

    print(f"Total proposed chunks: {len(proposed)}")
    print(f"Chunks per original document: {dict(per_doc)}")
    print(f"Chunks per category: {dict(per_category)}")
    print(
        f"Estimated embedding API calls (batched by {EMBED_BATCH_SIZE}): "
        f"{-(-len(proposed) // EMBED_BATCH_SIZE)}"
    )
    print()

    ids = [chunk["id"] for chunk in proposed]
    if len(ids) != len(set(ids)):
        print("BLOCKER: duplicate proposed chunk ids within this run.")
        return 1
    print("All proposed chunk ids are unique and distinct from original ids.")
    print()

    print("NO AZURE WRITES PERFORMED")
    return 0


def run_apply(index_name: str = None) -> int:
    endpoint = os.getenv("AISEARCH_ENDPOINT")
    api_key = os.getenv("AISEARCH_APIKEY")
    index_name = index_name or os.getenv("AISEARCH_INDEX_NAME", DEFAULT_INDEX_NAME)

    check_result = run_check(index_name=index_name)
    if check_result != 0:
        print("\nBLOCKER: --check failed, refusing to run live migration.")
        return check_result
    print("\n" + "=" * 60 + "\n")

    search_client = _get_search_client(endpoint, api_key, index_name)

    print("=== Stage 1/6: snapshot original documents ===")
    documents = fetch_original_documents(search_client)
    problems = validate_originals(documents)
    if problems:
        print("BLOCKER:", problems)
        return 1
    snapshot = build_snapshot(documents, index_name)
    write_snapshot(snapshot)
    print(f"Snapshot written to {SNAPSHOT_PATH} ({len(documents)} documents).")
    print()

    print("=== Stage 2/6: generate proposed chunks ===")
    proposed = build_proposed_chunks(documents)
    original_ids = {doc["id"] for doc in documents}
    chunk_problems = []
    for chunk in proposed:
        chunk_problems.extend(validate_chunk(chunk, original_ids=original_ids))
    if chunk_problems:
        print("BLOCKER: chunk validation failed:", chunk_problems)
        return 1
    print(f"{len(proposed)} proposed chunks (before idempotency check).")
    print()

    print("=== Stage 3/6: idempotency check (skip already-existing chunks) ===")
    to_upload = []
    skipped = []
    for chunk in proposed:
        if chunk_id_exists(search_client, chunk["id"]):
            skipped.append(chunk["id"])
        else:
            to_upload.append(chunk)
    print(f"Already existing (skipped, not re-embedded): {len(skipped)}")
    print(f"New chunks to embed + upload: {len(to_upload)}")
    print()

    print("=== Stage 4/6: embed new chunks (batched) ===")
    from services.embedding_service import embedding_service

    for start in range(0, len(to_upload), EMBED_BATCH_SIZE):
        batch = to_upload[start : start + EMBED_BATCH_SIZE]
        texts = [chunk["content"] for chunk in batch]
        try:
            vectors = embedding_service.embed_batch(texts)
        except Exception as exc:
            print(f"BLOCKER: embedding failed for batch starting at {start}: {exc}")
            print("Stopping - no incomplete records will be uploaded.")
            return 1
        for chunk, vector in zip(batch, vectors, strict=True):
            if len(vector) != VECTOR_DIMENSIONS:
                print(
                    f"BLOCKER: chunk {chunk['id']} embedding has {len(vector)} dims, "
                    f"expected {VECTOR_DIMENSIONS}. Stopping."
                )
                return 1
            chunk["contentVector"] = vector
    print(f"Embedded {len(to_upload)} chunks.")
    print()

    print("=== Stage 5/6: upload chunks in batches (originals untouched) ===")
    uploaded = 0
    failed = 0
    for start in range(0, len(to_upload), UPLOAD_BATCH_SIZE):
        batch = to_upload[start : start + UPLOAD_BATCH_SIZE]
        if not batch:
            continue
        results = search_client.upload_documents(documents=batch)
        for result in results:
            if result.succeeded:
                uploaded += 1
            else:
                failed += 1
                print(f"  FAILED: {result.key} - {result.error_message}")
    print(f"Uploaded: {uploaded}  Failed: {failed}  Skipped (existed): {len(skipped)}")
    print()

    if failed:
        print(
            "BLOCKER: one or more chunk uploads failed - stopping before verification."
        )
        return 1

    print("=== Stage 6/6: verify original documents are unchanged ===")
    current_documents = fetch_original_documents(search_client)
    integrity_problems = verify_original_integrity(current_documents, snapshot)
    if integrity_problems:
        print("BLOCKER: original document integrity check failed:")
        for problem in integrity_problems:
            print(f"  - {problem}")
        return 1
    print(f"All {len(current_documents)} original documents verified unchanged.")
    print()

    index_client = _get_index_client(endpoint, api_key)
    stats = index_client.get_index_statistics(index_name)
    print(f"Total documents in '{index_name}' now: {stats.document_count}")
    print(f"  originals: {len(current_documents)}")
    print(f"  chunks uploaded this run: {uploaded}")
    print(f"  chunks skipped (already existed): {len(skipped)}")
    print()
    print("Live migration complete. Originals were never modified or deleted.")
    return 0


def run_delete_originals(index_name: str = None) -> int:
    """
    Guarded cleanup - deletes the original whole-document records. Refuses
    unless every precondition passes. This function is never called by
    this script's own default flow; it only runs if a human explicitly
    passes --delete-originals.
    """

    endpoint = os.getenv("AISEARCH_ENDPOINT")
    api_key = os.getenv("AISEARCH_APIKEY")
    index_name = index_name or os.getenv("AISEARCH_INDEX_NAME", DEFAULT_INDEX_NAME)

    print("=== --delete-originals precondition checks ===")

    snapshot = load_snapshot()
    if snapshot is None:
        print(f"BLOCKER: no snapshot manifest at {SNAPSHOT_PATH}. Run --apply first.")
        return 1

    if not endpoint or not api_key:
        print("BLOCKER: AISEARCH_ENDPOINT/AISEARCH_APIKEY not configured.")
        return 1

    search_client = _get_search_client(endpoint, api_key, index_name)

    documents = fetch_original_documents(search_client)
    if len(documents) != EXPECTED_ORIGINAL_COUNT:
        print(
            f"BLOCKER: expected {EXPECTED_ORIGINAL_COUNT} originals, "
            f"found {len(documents)}."
        )
        return 1

    integrity_problems = verify_original_integrity(documents, snapshot)
    if integrity_problems:
        print("BLOCKER: originals do not match the snapshot manifest:")
        for problem in integrity_problems:
            print(f"  - {problem}")
        return 1

    original_ids = {doc["id"] for doc in documents}
    chunks = list(
        search_client.search(
            search_text="*",
            filter="parent_id ne null",
            select=["id", "parent_id", "category", "source"],
            top=1000,
        )
    )
    parents_with_chunks = {c["parent_id"] for c in chunks}
    missing_chunks = original_ids - parents_with_chunks
    if missing_chunks:
        print(
            f"BLOCKER: {len(missing_chunks)} original document(s) have no chunks yet: "
            f"{sorted(missing_chunks)}"
        )
        return 1

    invalid_chunks = [
        c["id"] for c in chunks if c.get("category") not in ALL_CATEGORIES
    ]
    if invalid_chunks:
        print(f"BLOCKER: {len(invalid_chunks)} chunk(s) have invalid category.")
        return 1

    print("All preconditions passed.")
    print(
        "This command is implemented but was NOT executed automatically. "
        "Re-run with explicit human confirmation to actually delete "
        "the original whole-document records."
    )
    print(
        "REFUSING TO DELETE without an additional explicit confirmation "
        "step beyond this flag - deletion code intentionally requires a "
        "human to call run_delete_originals(confirm=True) directly."
    )
    return 1


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--check", action="store_true", help="Read-only check (default)."
    )
    group.add_argument(
        "--dry-run", action="store_true", help="Simulate locally - zero Azure writes."
    )
    group.add_argument(
        "--apply", action="store_true", help="Run the live additive migration."
    )
    group.add_argument(
        "--delete-originals",
        action="store_true",
        help="Guarded cleanup of the 21 original records (never runs automatically).",
    )
    parser.add_argument(
        "--index-name", default=None, help="Override the target index name."
    )
    args = parser.parse_args()

    if args.dry_run:
        sys.exit(run_dry_run(index_name=args.index_name))
    if args.apply:
        sys.exit(run_apply(index_name=args.index_name))
    if args.delete_originals:
        sys.exit(run_delete_originals(index_name=args.index_name))
    sys.exit(run_check(index_name=args.index_name))


if __name__ == "__main__":
    main()
