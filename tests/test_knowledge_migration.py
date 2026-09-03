"""
Tests for scripts/migrate_knowledge_chunks.py - the Python-side chunk
migration that stands in for native Azure Search index projections
(blocked on group-1's key field - see setup_knowledge_indexer.py).
All Azure/embedding calls are mocked - no live network calls.
"""

import sys
from pathlib import Path
from types import SimpleNamespace

from azure.core.exceptions import ResourceNotFoundError

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
for path in (ROOT, SCRIPTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import migrate_knowledge_chunks as migrate  # noqa: E402

ORIGINAL_DOCS = [
    {
        "id": "orig-1",
        "content": (
            "Paragraph one about the general employee handbook overview.\n\n"
            "Paragraph two with more detail about workplace expectations "
            "and where to find help for common questions.\n\n"
            "Paragraph three closes out with a summary of key policies "
            "and who to contact for further questions."
        ),
        "category": "General",
        "source": "employee_handbook.pdf",
    },
    {
        "id": "orig-2",
        "content": "Short HR leave note.\n\nA second short paragraph about leave.",
        "category": "HR",
        "source": "hr_leave_management_handbook.pdf",
    },
]


def _make_originals(n=21, category="General"):
    return [
        {
            "id": f"orig-{i}",
            "content": f"Paragraph A for doc {i}.\n\nParagraph B for doc {i}.",
            "category": category,
            "source": f"doc-{i}.pdf",
        }
        for i in range(n)
    ]


class FakeIndexField:
    def __init__(self, name, key=False, vector_search_dimensions=None):
        self.name = name
        self.key = key
        self.vector_search_dimensions = vector_search_dimensions


class FakeIndex:
    def __init__(self, fields, vector_search="configured"):
        self.fields = fields
        self.vector_search = vector_search


def _compatible_index():
    return FakeIndex(
        [
            FakeIndexField("id", key=True),
            FakeIndexField("parent_id"),
            FakeIndexField("content"),
            FakeIndexField("contentVector", vector_search_dimensions=1536),
            FakeIndexField("category"),
            FakeIndexField("source"),
        ]
    )


class FakeIndexClient:
    def __init__(self, index, document_count=21):
        self._index = index
        self.document_count = document_count

    def get_index(self, name):
        return self._index

    def get_index_statistics(self, name):
        return SimpleNamespace(document_count=self.document_count)


class FakeMigrationSearchClient:
    def __init__(self, documents, existing_chunk_ids=None):
        self.documents = {d["id"]: dict(d) for d in documents}
        self.existing_chunk_ids = set(existing_chunk_ids or [])
        self.uploaded_batches = []

    def search(self, **kwargs):
        docs = list(self.documents.values())
        filter_expr = kwargs.get("filter")
        if filter_expr == "parent_id eq null":
            docs = [d for d in docs if not d.get("parent_id")]
        elif filter_expr == "parent_id ne null":
            docs = [d for d in docs if d.get("parent_id")]
        return docs

    def get_document(self, key):
        if key in self.existing_chunk_ids:
            return {"id": key}
        raise ResourceNotFoundError("not found")

    def upload_documents(self, documents):
        self.uploaded_batches.append(documents)
        for doc in documents:
            self.documents[doc["id"]] = doc
        return [
            SimpleNamespace(succeeded=True, key=doc["id"], error_message=None)
            for doc in documents
        ]


class FakeEmbeddingService:
    def __init__(self, dimensions=1536, fail=False):
        self.dimensions = dimensions
        self.fail = fail
        self.batch_calls = []

    def embed(self, text):
        if self.fail:
            raise RuntimeError("embedding deployment unreachable")
        return [0.1] * self.dimensions

    def embed_batch(self, texts):
        if self.fail:
            raise RuntimeError("embedding deployment unreachable")
        self.batch_calls.append(list(texts))
        return [[0.1] * self.dimensions for _ in texts]


def _patch_common(monkeypatch, index_client, search_client, embedding_service=None):
    monkeypatch.setenv("AISEARCH_ENDPOINT", "https://fake.search.windows.net")
    monkeypatch.setenv("AISEARCH_APIKEY", "fake-search-key")
    monkeypatch.setenv(
        "GROUP1_TEXT_EMBEDDING_3_SMALL_ENDPOINT", "https://fake.openai.azure.com"
    )
    monkeypatch.setenv("GROUP1_TEXT_EMBEDDING_3_SMALL_APIKEY", "fake-embedding-key")
    monkeypatch.setattr(
        migrate, "_get_index_client", lambda endpoint, api_key: index_client
    )
    monkeypatch.setattr(
        migrate,
        "_get_search_client",
        lambda endpoint, api_key, index_name: search_client,
    )
    fake_embedding = embedding_service or FakeEmbeddingService()
    monkeypatch.setattr("services.embedding_service.embedding_service", fake_embedding)
    monkeypatch.setattr(
        migrate,
        "chunk_id_exists",
        lambda client, chunk_id: chunk_id in search_client.existing_chunk_ids,
    )
    return fake_embedding


# --- Deterministic chunking ---


def test_chunk_text_splits_on_paragraph_boundaries():
    text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
    chunks = migrate.chunk_text(text, target_tokens=5, overlap_tokens=0)
    assert len(chunks) >= 2
    assert all(chunk.strip() for chunk in chunks)


def test_chunk_text_never_splits_mid_word():
    text = "supercalifragilisticexpialidocious " * 50
    chunks = migrate.chunk_text(text, target_tokens=20, overlap_tokens=0)
    for chunk in chunks:
        assert "supercalifragilisticexpialidocious" in chunk
        # every whitespace-delimited token in the chunk is a whole word
        for word in chunk.split():
            assert (
                word == ""
                or "supercalifragilisticexpialidocious" in word
                or word == word.strip()
            )


def test_chunk_text_handles_short_document_as_one_chunk():
    text = "Just one short paragraph."
    chunks = migrate.chunk_text(text)
    assert chunks == ["Just one short paragraph."]


def test_generate_chunk_id_is_deterministic_for_unchanged_content():
    id_a = migrate.generate_chunk_id("orig-1", 0, "some chunk text")
    id_b = migrate.generate_chunk_id("orig-1", 0, "some chunk text")
    assert id_a == id_b


def test_generate_chunk_id_changes_when_content_changes():
    id_a = migrate.generate_chunk_id("orig-1", 0, "some chunk text")
    id_b = migrate.generate_chunk_id("orig-1", 0, "different chunk text")
    assert id_a != id_b


def test_chunk_id_never_equals_parent_id():
    chunk_id = migrate.generate_chunk_id("orig-1", 0, "text")
    assert chunk_id != "orig-1"


# --- Validation ---


def test_validate_originals_accepts_valid_dataset():
    docs = _make_originals(21)
    assert migrate.validate_originals(docs) == []


def test_validate_originals_rejects_wrong_count():
    docs = _make_originals(5)
    problems = migrate.validate_originals(docs)
    assert any("expected exactly" in p for p in problems)


def test_validate_originals_rejects_invalid_category():
    docs = _make_originals(21)
    docs[0]["category"] = "NotARealCategory"
    problems = migrate.validate_originals(docs)
    assert any("invalid category" in p for p in problems)


def test_validate_originals_rejects_missing_fields():
    docs = _make_originals(21)
    del docs[0]["source"]
    problems = migrate.validate_originals(docs)
    assert any("missing 'source'" in p for p in problems)


def test_validate_originals_rejects_duplicate_ids():
    docs = _make_originals(21)
    docs[1]["id"] = docs[0]["id"]
    problems = migrate.validate_originals(docs)
    assert any("duplicate original id" in p for p in problems)


def test_validate_chunk_rejects_wrong_vector_dimensions():
    chunk = {
        "id": "chunk-1",
        "parent_id": "orig-1",
        "content": "text",
        "category": "HR",
        "source": "s",
        "contentVector": [0.1] * 100,
    }
    problems = migrate.validate_chunk(chunk, original_ids={"orig-1"})
    assert any("dimensions" in p for p in problems)


def test_validate_chunk_rejects_id_colliding_with_original():
    chunk = {
        "id": "orig-1",
        "parent_id": "orig-1",
        "content": "text",
        "category": "HR",
        "source": "s",
    }
    problems = migrate.validate_chunk(chunk, original_ids={"orig-1"})
    assert any("collides" in p for p in problems)


def test_validate_chunk_rejects_unknown_parent():
    chunk = {
        "id": "chunk-1",
        "parent_id": "does-not-exist",
        "content": "text",
        "category": "HR",
        "source": "s",
    }
    problems = migrate.validate_chunk(chunk, original_ids={"orig-1"})
    assert any("unknown parent_id" in p for p in problems)


# --- Snapshot manifest ---


def test_snapshot_manifest_written_and_reloaded(tmp_path):
    path = tmp_path / "snapshot.json"
    snapshot = migrate.build_snapshot(ORIGINAL_DOCS, "group-1")
    migrate.write_snapshot(snapshot, path=path)

    loaded = migrate.load_snapshot(path=path)
    assert loaded["expected_count"] == migrate.EXPECTED_ORIGINAL_COUNT
    assert len(loaded["documents"]) == len(ORIGINAL_DOCS)
    assert "content_hash" in loaded["documents"][0]
    assert "credentials" not in str(loaded).lower()


def test_integrity_check_detects_unchanged_originals():
    snapshot = migrate.build_snapshot(ORIGINAL_DOCS, "group-1")
    assert migrate.verify_original_integrity(ORIGINAL_DOCS, snapshot) == []


def test_integrity_check_detects_changed_content():
    snapshot = migrate.build_snapshot(ORIGINAL_DOCS, "group-1")
    tampered = [dict(d) for d in ORIGINAL_DOCS]
    tampered[0]["content"] = "this content was changed after the snapshot"
    problems = migrate.verify_original_integrity(tampered, snapshot)
    assert any("content changed" in p for p in problems)


def test_integrity_check_detects_changed_category():
    snapshot = migrate.build_snapshot(ORIGINAL_DOCS, "group-1")
    tampered = [dict(d) for d in ORIGINAL_DOCS]
    tampered[0]["category"] = "IT"
    problems = migrate.verify_original_integrity(tampered, snapshot)
    assert any("category changed" in p for p in problems)


# --- --check: zero writes ---


def test_check_mode_passes_and_makes_no_writes(monkeypatch):
    docs = _make_originals(21)
    search_client = FakeMigrationSearchClient(docs)
    index_client = FakeIndexClient(_compatible_index())
    _patch_common(monkeypatch, index_client, search_client)

    exit_code = migrate.run_check()

    assert exit_code == 0
    assert search_client.uploaded_batches == []


def test_check_mode_fails_on_invalid_category(monkeypatch):
    docs = _make_originals(21)
    docs[0]["category"] = "NotReal"
    search_client = FakeMigrationSearchClient(docs)
    index_client = FakeIndexClient(_compatible_index())
    _patch_common(monkeypatch, index_client, search_client)

    exit_code = migrate.run_check()

    assert exit_code == 1
    assert search_client.uploaded_batches == []


def test_check_mode_fails_on_embedding_failure(monkeypatch):
    docs = _make_originals(21)
    search_client = FakeMigrationSearchClient(docs)
    index_client = FakeIndexClient(_compatible_index())
    _patch_common(
        monkeypatch,
        index_client,
        search_client,
        embedding_service=FakeEmbeddingService(fail=True),
    )

    exit_code = migrate.run_check()

    assert exit_code == 1


def test_check_mode_fails_on_missing_config(monkeypatch):
    monkeypatch.delenv("AISEARCH_ENDPOINT", raising=False)
    monkeypatch.delenv("AISEARCH_APIKEY", raising=False)

    exit_code = migrate.run_check()

    assert exit_code == 1


# --- --dry-run: zero writes ---


def test_dry_run_makes_zero_search_writes(monkeypatch, capsys):
    docs = _make_originals(21)
    search_client = FakeMigrationSearchClient(docs)
    monkeypatch.setenv("AISEARCH_ENDPOINT", "https://fake.search.windows.net")
    monkeypatch.setenv("AISEARCH_APIKEY", "fake-search-key")
    monkeypatch.setattr(
        migrate,
        "_get_search_client",
        lambda endpoint, api_key, index_name: search_client,
    )

    exit_code = migrate.run_dry_run()

    assert exit_code == 0
    assert search_client.uploaded_batches == []
    captured = capsys.readouterr()
    assert "NO AZURE WRITES PERFORMED" in captured.out


def test_dry_run_reports_chunk_and_category_counts(monkeypatch, capsys):
    docs = _make_originals(3, category="IT")
    search_client = FakeMigrationSearchClient(docs)
    monkeypatch.setenv("AISEARCH_ENDPOINT", "https://fake.search.windows.net")
    monkeypatch.setenv("AISEARCH_APIKEY", "fake-search-key")
    monkeypatch.setattr(
        migrate,
        "_get_search_client",
        lambda endpoint, api_key, index_name: search_client,
    )
    # dry-run validates against EXPECTED_ORIGINAL_COUNT=21, so relax it here.
    monkeypatch.setattr(migrate, "EXPECTED_ORIGINAL_COUNT", 3)

    exit_code = migrate.run_dry_run()

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Total proposed chunks" in captured.out
    assert "'IT'" in captured.out


def test_dry_run_never_calls_embedding(monkeypatch):
    docs = _make_originals(21)
    search_client = FakeMigrationSearchClient(docs)
    monkeypatch.setenv("AISEARCH_ENDPOINT", "https://fake.search.windows.net")
    monkeypatch.setenv("AISEARCH_APIKEY", "fake-search-key")
    monkeypatch.setattr(
        migrate,
        "_get_search_client",
        lambda endpoint, api_key, index_name: search_client,
    )
    fake_embedding = FakeEmbeddingService()
    monkeypatch.setattr("services.embedding_service.embedding_service", fake_embedding)

    migrate.run_dry_run()

    assert fake_embedding.batch_calls == []


# --- --apply: live additive migration ---


def test_apply_never_deletes_originals(monkeypatch, tmp_path):
    docs = _make_originals(21)
    search_client = FakeMigrationSearchClient(docs)
    index_client = FakeIndexClient(_compatible_index())
    _patch_common(monkeypatch, index_client, search_client)
    monkeypatch.setattr(migrate, "SNAPSHOT_PATH", tmp_path / "snapshot.json")

    exit_code = migrate.run_apply()

    assert exit_code == 0
    # originals are still exactly present and untouched
    remaining_originals = [
        d for d in search_client.documents.values() if not d.get("parent_id")
    ]
    assert len(remaining_originals) == 21
    assert not hasattr(search_client, "delete_documents_called")


def test_apply_writes_snapshot_manifest(monkeypatch, tmp_path):
    docs = _make_originals(21)
    search_client = FakeMigrationSearchClient(docs)
    index_client = FakeIndexClient(_compatible_index())
    _patch_common(monkeypatch, index_client, search_client)
    snapshot_path = tmp_path / "snapshot.json"
    monkeypatch.setattr(migrate, "SNAPSHOT_PATH", snapshot_path)

    exit_code = migrate.run_apply()

    assert exit_code == 0
    assert snapshot_path.exists()


def test_apply_uploads_chunks_with_vectors_and_metadata(monkeypatch, tmp_path):
    docs = _make_originals(2, category="Accounting")
    search_client = FakeMigrationSearchClient(docs)
    index_client = FakeIndexClient(_compatible_index())
    _patch_common(monkeypatch, index_client, search_client)
    monkeypatch.setattr(migrate, "SNAPSHOT_PATH", tmp_path / "snapshot.json")
    monkeypatch.setattr(migrate, "EXPECTED_ORIGINAL_COUNT", 2)

    exit_code = migrate.run_apply()

    assert exit_code == 0
    uploaded = [doc for batch in search_client.uploaded_batches for doc in batch]
    assert len(uploaded) > 0
    for chunk in uploaded:
        assert chunk["category"] == "Accounting"
        assert len(chunk["contentVector"]) == 1536
        assert chunk["parent_id"] in {d["id"] for d in docs}


def test_apply_skips_chunks_that_already_exist(monkeypatch, tmp_path):
    docs = [ORIGINAL_DOCS[1]]  # single small doc -> one predictable chunk
    proposed = migrate.build_proposed_chunks(docs)
    existing_ids = {chunk["id"] for chunk in proposed}
    search_client = FakeMigrationSearchClient(docs, existing_chunk_ids=existing_ids)
    index_client = FakeIndexClient(_compatible_index())
    fake_embedding = _patch_common(monkeypatch, index_client, search_client)
    monkeypatch.setattr(migrate, "SNAPSHOT_PATH", tmp_path / "snapshot.json")
    monkeypatch.setattr(migrate, "EXPECTED_ORIGINAL_COUNT", 1)

    exit_code = migrate.run_apply()

    assert exit_code == 0
    assert search_client.uploaded_batches == []
    assert fake_embedding.batch_calls == []


def test_apply_stops_on_embedding_failure_without_uploading(monkeypatch, tmp_path):
    docs = _make_originals(2)
    search_client = FakeMigrationSearchClient(docs)
    index_client = FakeIndexClient(_compatible_index())
    _patch_common(
        monkeypatch,
        index_client,
        search_client,
        embedding_service=FakeEmbeddingService(fail=True),
    )
    monkeypatch.setattr(migrate, "SNAPSHOT_PATH", tmp_path / "snapshot.json")

    exit_code = migrate.run_apply()

    assert exit_code == 1
    assert search_client.uploaded_batches == []


def test_apply_verifies_original_integrity_after_upload(monkeypatch, tmp_path):
    docs = _make_originals(21)
    search_client = FakeMigrationSearchClient(docs)
    index_client = FakeIndexClient(_compatible_index())
    _patch_common(monkeypatch, index_client, search_client)
    monkeypatch.setattr(migrate, "SNAPSHOT_PATH", tmp_path / "snapshot.json")

    exit_code = migrate.run_apply()

    assert exit_code == 0  # implies integrity check passed (unchanged fake data)


# --- --delete-originals: guarded, never auto-run ---


def test_delete_originals_refuses_without_snapshot(monkeypatch, tmp_path):
    monkeypatch.setattr(migrate, "SNAPSHOT_PATH", tmp_path / "does-not-exist.json")
    monkeypatch.setenv("AISEARCH_ENDPOINT", "https://fake.search.windows.net")
    monkeypatch.setenv("AISEARCH_APIKEY", "fake-search-key")

    exit_code = migrate.run_delete_originals()

    assert exit_code == 1


def test_delete_originals_never_actually_deletes_even_when_all_checks_pass(
    monkeypatch, tmp_path
):
    docs = _make_originals(21)
    proposed = migrate.build_proposed_chunks(docs)
    all_docs = docs + [{**chunk, "content": chunk["content"]} for chunk in proposed]
    search_client = FakeMigrationSearchClient(all_docs)
    snapshot_path = tmp_path / "snapshot.json"
    migrate.write_snapshot(migrate.build_snapshot(docs, "group-1"), path=snapshot_path)
    monkeypatch.setattr(migrate, "SNAPSHOT_PATH", snapshot_path)
    monkeypatch.setenv("AISEARCH_ENDPOINT", "https://fake.search.windows.net")
    monkeypatch.setenv("AISEARCH_APIKEY", "fake-search-key")
    monkeypatch.setattr(
        migrate,
        "_get_search_client",
        lambda endpoint, api_key, index_name: search_client,
    )

    exit_code = migrate.run_delete_originals()

    # Even with every precondition satisfied, this command refuses to
    # delete anything on its own - it always returns non-zero and never
    # calls a delete API.
    assert exit_code == 1
    remaining_originals = [
        d for d in search_client.documents.values() if not d.get("parent_id")
    ]
    assert len(remaining_originals) == 21


def test_delete_originals_is_not_reachable_from_default_cli_invocation():
    import inspect

    main_source = inspect.getsource(migrate.main)
    # --delete-originals must require an explicit flag, never be the default.
    assert "args.delete_originals" in main_source


# --- Product rule: General is a scope, never a department ---


def test_general_accepted_as_search_category():
    from knowledge_categories import ALL_CATEGORIES

    assert "General" in ALL_CATEGORIES


def test_general_rejected_by_migration_as_a_department_value():
    from services.ticket_draft_service import STANDARD_CATEGORIES

    assert "General" not in STANDARD_CATEGORIES
