"""
Tests for the Blob -> Azure AI Search ingestion setup scripts. All Azure
SDK calls are mocked/faked - no live network calls, no secrets involved.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
for path in (ROOT, SCRIPTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import knowledge_categories  # noqa: E402
import set_blob_category_metadata  # noqa: E402
import setup_knowledge_indexer  # noqa: E402

# --- knowledge_categories.py: deterministic mapping ---


def test_category_for_blob_returns_mapped_category():
    assert (
        knowledge_categories.category_for_blob("hr_leave_management_handbook.pdf")
        == "HR"
    )


def test_category_for_blob_raises_for_unmapped_blob():
    with pytest.raises(KeyError):
        knowledge_categories.category_for_blob("some_new_unmapped_file.pdf")


def test_all_mapped_categories_are_known_categories():
    unknown = {
        category
        for category in knowledge_categories.BLOB_CATEGORY_MAP.values()
        if category not in knowledge_categories.ALL_CATEGORIES
    }
    assert unknown == set()


def test_mapping_is_deterministic():
    name = "employee_handbook.pdf"
    assert (
        knowledge_categories.category_for_blob(name)
        == knowledge_categories.category_for_blob(name)
        == "General"
    )


# --- set_blob_category_metadata.py ---


def test_blob_metadata_script_fails_safely_with_no_usable_credential(monkeypatch):
    # No key/connection-string configured, and the fallback identity-based
    # path (DefaultAzureCredential) has no usable credential either - this
    # must fail safely offline, without ever needing a live network call.
    monkeypatch.delenv("AZURE_STORAGE_CONNECTION_STRING", raising=False)
    monkeypatch.delenv("AZURE_STORAGE_ACCOUNT_KEY", raising=False)
    monkeypatch.setattr(
        set_blob_category_metadata,
        "_get_container_client",
        lambda: (_ for _ in ()).throw(RuntimeError("no usable credential")),
    )

    exit_code = set_blob_category_metadata.run(apply_changes=False)
    assert exit_code == 1


def test_blob_metadata_reports_rbac_role_needed_on_authorization_failure(
    monkeypatch, capsys
):
    class _RaisingContainerClient:
        def list_blobs(self):
            raise Exception(
                "Server failed to authenticate the request. "
                "AuthorizationPermissionMismatch"
            )

    monkeypatch.setattr(
        set_blob_category_metadata,
        "_get_container_client",
        lambda: _RaisingContainerClient(),
    )

    exit_code = set_blob_category_metadata.run(apply_changes=False)

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Storage Blob Data Reader" in captured.out


class _FakeBlobProps:
    def __init__(self, name, metadata=None):
        self.name = name
        self.metadata = metadata or {}


class _FakeBlobClient:
    def __init__(self, container, name):
        self._container = container
        self._name = name

    def get_blob_properties(self):
        return _FakeBlobProps(self._name, self._container.blob_metadata.get(self._name))

    def set_blob_metadata(self, metadata):
        self._container.set_calls.append((self._name, dict(metadata)))
        self._container.blob_metadata[self._name] = metadata


class _FakeContainerClient:
    def __init__(self, blob_names, blob_metadata=None):
        self.blob_names = blob_names
        self.blob_metadata = blob_metadata or {}
        self.set_calls = []

    def list_blobs(self):
        return [
            _FakeBlobProps(name, self.blob_metadata.get(name))
            for name in self.blob_names
        ]

    def get_blob_client(self, name):
        return _FakeBlobClient(self, name)


def test_blob_metadata_check_mode_makes_no_writes(monkeypatch):
    container = _FakeContainerClient(
        ["employee_handbook.pdf", "it_support_playbook.pdf"]
    )
    monkeypatch.setattr(
        set_blob_category_metadata, "_get_container_client", lambda: container
    )

    exit_code = set_blob_category_metadata.run(apply_changes=False)

    assert exit_code == 0
    assert container.set_calls == []


def test_blob_metadata_apply_writes_only_missing_or_changed(monkeypatch):
    container = _FakeContainerClient(
        blob_names=["employee_handbook.pdf", "it_support_playbook.pdf"],
        blob_metadata={"employee_handbook.pdf": {"category": "General"}},
    )
    monkeypatch.setattr(
        set_blob_category_metadata, "_get_container_client", lambda: container
    )

    exit_code = set_blob_category_metadata.run(apply_changes=True)

    assert exit_code == 0
    # employee_handbook.pdf was already correct -> not rewritten.
    assert [name for name, _ in container.set_calls] == ["it_support_playbook.pdf"]
    assert container.set_calls[0][1]["category"] == "IT"


def test_blob_metadata_apply_refuses_when_unmapped_blob_present(monkeypatch):
    container = _FakeContainerClient(["totally_unmapped_file.pdf"])
    monkeypatch.setattr(
        set_blob_category_metadata, "_get_container_client", lambda: container
    )

    exit_code = set_blob_category_metadata.run(apply_changes=True)

    assert exit_code == 1
    assert container.set_calls == []


def test_blob_metadata_never_logs_secrets(monkeypatch, capsys):
    secret = "super-secret-account-key-value"
    monkeypatch.setenv("AZURE_STORAGE_ACCOUNT_NAME", "seed123data")
    monkeypatch.setenv("AZURE_STORAGE_ACCOUNT_KEY", secret)
    container = _FakeContainerClient(["employee_handbook.pdf"])
    monkeypatch.setattr(
        set_blob_category_metadata, "_get_container_client", lambda: container
    )

    set_blob_category_metadata.run(apply_changes=False)

    captured = capsys.readouterr()
    assert secret not in captured.out
    assert secret not in captured.err


# --- setup_knowledge_indexer.py ---


def test_indexer_script_fails_safely_without_search_config(monkeypatch):
    monkeypatch.delenv("AISEARCH_ENDPOINT", raising=False)
    monkeypatch.delenv("AISEARCH_APIKEY", raising=False)

    exit_code = setup_knowledge_indexer.run(apply_changes=False)
    assert exit_code == 1


class _FakeField:
    def __init__(self, name, key=False):
        self.name = name
        self.key = key


class _FakeIndex:
    def __init__(self, fields):
        self.fields = fields


class _FakeStats:
    def __init__(self, document_count):
        self.document_count = document_count


class _FakeIndexClient:
    def __init__(self, index, document_count=21):
        self._index = index
        self._document_count = document_count
        self.updated_indexes = []

    def get_index(self, name):
        return self._index

    def create_or_update_index(self, index):
        self.updated_indexes.append(index)
        self._index = index

    def get_index_statistics(self, name):
        return _FakeStats(self._document_count)


class _FakeIndexerClient:
    def __init__(
        self, data_sources=(), indexers=(), skillsets=(), indexer_by_name=None
    ):
        self._data_sources = list(data_sources)
        self._indexers = list(indexers)
        self._skillsets = list(skillsets)
        self._indexer_by_name = dict(indexer_by_name or {})
        self.created_data_sources = []
        self.created_indexers = []
        self.updated_skillsets = []
        self.updated_indexers = []
        self.run_calls = []
        self.reset_calls = []

    def get_data_source_connection_names(self):
        return list(self._data_sources)

    def get_indexer_names(self):
        return list(self._indexers)

    def get_skillset_names(self):
        return list(self._skillsets)

    def get_indexer(self, name):
        return self._indexer_by_name.get(name, _FakeSimpleIndexer(skillset_name=None))

    def create_data_source_connection(self, data_source):
        self.created_data_sources.append(data_source)
        self._data_sources.append(data_source.name)

    def create_indexer(self, indexer):
        self.created_indexers.append(indexer)
        self._indexers.append(indexer.name)

    def create_or_update_skillset(self, skillset):
        self.updated_skillsets.append(skillset)
        self._skillsets.append(skillset.name)

    def create_or_update_indexer(self, indexer):
        self.updated_indexers.append(indexer)
        self._indexer_by_name[indexer.name] = indexer

    def reset_indexer(self, name):
        self.reset_calls.append(name)

    def run_indexer(self, name):
        self.run_calls.append(name)


class _FakeSimpleIndexer:
    def __init__(self, skillset_name):
        self.skillset_name = skillset_name


def _compatible_index():
    return _FakeIndex(
        [
            _FakeField("id", key=True),
            _FakeField("content"),
            _FakeField("category"),
            _FakeField("source"),
        ]
    )


def _patch_search_clients(monkeypatch, index, indexer_client):
    monkeypatch.setenv("AISEARCH_ENDPOINT", "https://fake.search.windows.net")
    monkeypatch.setenv("AISEARCH_APIKEY", "fake-search-key")
    monkeypatch.setenv("AZURE_STORAGE_ACCOUNT_NAME", "seed123data")
    monkeypatch.setenv("AZURE_STORAGE_ACCOUNT_KEY", "fake-storage-key")
    monkeypatch.setattr(
        setup_knowledge_indexer,
        "_get_search_clients",
        lambda endpoint, api_key: (_FakeIndexClient(index), indexer_client),
    )


def test_indexer_check_mode_makes_no_azure_changes(monkeypatch):
    indexer_client = _FakeIndexerClient()
    _patch_search_clients(monkeypatch, _compatible_index(), indexer_client)

    exit_code = setup_knowledge_indexer.run(apply_changes=False)

    assert exit_code == 0
    assert indexer_client.created_data_sources == []
    assert indexer_client.created_indexers == []
    assert indexer_client.run_calls == []


def test_indexer_apply_creates_data_source_and_indexer_when_missing(monkeypatch):
    indexer_client = _FakeIndexerClient()
    _patch_search_clients(monkeypatch, _compatible_index(), indexer_client)

    exit_code = setup_knowledge_indexer.run(apply_changes=True)

    assert exit_code == 0
    assert len(indexer_client.created_data_sources) == 1
    assert len(indexer_client.created_indexers) == 1
    assert indexer_client.run_calls == [setup_knowledge_indexer.INDEXER_NAME]
    # Never targets/creates a different index.
    assert (
        indexer_client.created_indexers[0].target_index_name
        == setup_knowledge_indexer.DEFAULT_INDEX_NAME
    )


def test_indexer_apply_reuses_existing_data_source_and_indexer(monkeypatch):
    indexer_client = _FakeIndexerClient(
        data_sources=[setup_knowledge_indexer.DATA_SOURCE_NAME],
        indexers=[setup_knowledge_indexer.INDEXER_NAME],
    )
    _patch_search_clients(monkeypatch, _compatible_index(), indexer_client)

    exit_code = setup_knowledge_indexer.run(apply_changes=True)

    assert exit_code == 0
    assert indexer_client.created_data_sources == []
    assert indexer_client.created_indexers == []
    assert indexer_client.run_calls == [setup_knowledge_indexer.INDEXER_NAME]


def test_indexer_refuses_incompatible_index_schema(monkeypatch):
    incompatible_index = _FakeIndex(
        [_FakeField("id", key=True), _FakeField("content")]  # missing category/source
    )
    indexer_client = _FakeIndexerClient()
    _patch_search_clients(monkeypatch, incompatible_index, indexer_client)

    exit_code = setup_knowledge_indexer.run(apply_changes=True)

    assert exit_code == 1
    assert indexer_client.created_data_sources == []
    assert indexer_client.created_indexers == []


# --- Hybrid (chunked + vector) upgrade ---


def _patch_hybrid(monkeypatch, index, indexer_client, dimensions=1536):
    monkeypatch.setenv("AISEARCH_ENDPOINT", "https://fake.search.windows.net")
    monkeypatch.setenv("AISEARCH_APIKEY", "fake-search-key")
    monkeypatch.setenv(
        "GROUP1_TEXT_EMBEDDING_3_SMALL_ENDPOINT", "https://fake.openai.azure.com"
    )
    monkeypatch.setenv("GROUP1_TEXT_EMBEDDING_3_SMALL_APIKEY", "fake-embedding-key")
    monkeypatch.setattr(
        setup_knowledge_indexer,
        "_get_search_clients",
        lambda endpoint, api_key: (index, indexer_client),
    )
    monkeypatch.setattr(
        setup_knowledge_indexer,
        "_verify_embedding_deployment",
        lambda endpoint, api_key: dimensions,
    )


def test_hybrid_check_fails_safely_without_embedding_config(monkeypatch):
    monkeypatch.setenv("AISEARCH_ENDPOINT", "https://fake.search.windows.net")
    monkeypatch.setenv("AISEARCH_APIKEY", "fake-search-key")
    monkeypatch.delenv("GROUP1_TEXT_EMBEDDING_3_SMALL_ENDPOINT", raising=False)
    monkeypatch.delenv("GROUP1_TEXT_EMBEDDING_3_SMALL_APIKEY", raising=False)

    exit_code = setup_knowledge_indexer.run_hybrid_upgrade(apply_changes=False)
    assert exit_code == 1


def test_hybrid_check_fails_safely_on_dimension_mismatch(monkeypatch):
    index_client = _FakeIndexClient(_compatible_index())
    indexer_client = _FakeIndexerClient(
        indexer_by_name={
            setup_knowledge_indexer.INDEXER_NAME: _FakeSimpleIndexer(skillset_name=None)
        }
    )
    _patch_hybrid(monkeypatch, index_client, indexer_client, dimensions=3072)

    exit_code = setup_knowledge_indexer.run_hybrid_upgrade(apply_changes=False)

    assert exit_code == 1
    assert index_client.updated_indexes == []


def test_hybrid_check_mode_makes_no_azure_changes(monkeypatch):
    index_client = _FakeIndexClient(_compatible_index())
    indexer_client = _FakeIndexerClient(
        indexer_by_name={
            setup_knowledge_indexer.INDEXER_NAME: _FakeSimpleIndexer(skillset_name=None)
        }
    )
    _patch_hybrid(monkeypatch, index_client, indexer_client)

    exit_code = setup_knowledge_indexer.run_hybrid_upgrade(apply_changes=False)

    assert exit_code == 0
    assert index_client.updated_indexes == []
    assert indexer_client.updated_skillsets == []
    assert indexer_client.updated_indexers == []
    assert indexer_client.reset_calls == []
    assert indexer_client.run_calls == []


def test_hybrid_apply_adds_fields_without_removing_existing_ones(monkeypatch):
    index_client = _FakeIndexClient(_compatible_index())
    indexer_client = _FakeIndexerClient(
        indexer_by_name={
            setup_knowledge_indexer.INDEXER_NAME: _FakeSimpleIndexer(skillset_name=None)
        }
    )
    _patch_hybrid(monkeypatch, index_client, indexer_client)

    exit_code = setup_knowledge_indexer.run_hybrid_upgrade(apply_changes=True)

    assert exit_code == 0
    updated_index = index_client.updated_indexes[0]
    field_names = {f.name for f in updated_index.fields}
    # Original fields preserved, new ones added.
    assert {"id", "content", "category", "source", "parent_id", "contentVector"} <= (
        field_names
    )
    assert updated_index.vector_search is not None


def test_hybrid_apply_creates_skillset_and_updates_indexer(monkeypatch):
    index_client = _FakeIndexClient(_compatible_index())
    indexer_client = _FakeIndexerClient(
        indexer_by_name={
            setup_knowledge_indexer.INDEXER_NAME: _FakeSimpleIndexer(skillset_name=None)
        }
    )
    _patch_hybrid(monkeypatch, index_client, indexer_client)

    exit_code = setup_knowledge_indexer.run_hybrid_upgrade(apply_changes=True)

    assert exit_code == 0
    assert len(indexer_client.updated_skillsets) == 1
    assert (
        indexer_client.updated_skillsets[0].name
        == setup_knowledge_indexer.SKILLSET_NAME
    )
    updated_indexer = indexer_client.updated_indexers[0]
    assert updated_indexer.skillset_name == setup_knowledge_indexer.SKILLSET_NAME
    assert (
        updated_indexer.target_index_name == setup_knowledge_indexer.DEFAULT_INDEX_NAME
    )
    assert indexer_client.reset_calls == [setup_knowledge_indexer.INDEXER_NAME]
    assert indexer_client.run_calls == [setup_knowledge_indexer.INDEXER_NAME]


def test_hybrid_apply_refuses_incompatible_base_schema(monkeypatch):
    incompatible_index = _FakeIndex([_FakeField("id", key=True), _FakeField("content")])
    index_client = _FakeIndexClient(incompatible_index)
    indexer_client = _FakeIndexerClient()
    _patch_hybrid(monkeypatch, index_client, indexer_client)

    exit_code = setup_knowledge_indexer.run_hybrid_upgrade(apply_changes=True)

    assert exit_code == 1
    assert index_client.updated_indexes == []
    assert indexer_client.updated_skillsets == []


def test_indexer_script_never_creates_or_deletes_the_index():
    """
    Structural guard: the setup module may use create_or_update_index() to
    ADD fields to the existing index (the sanctioned in-place hybrid
    upgrade), but must never call the create-only or delete APIs that
    would make/remove a whole index.
    """
    import inspect

    source = inspect.getsource(setup_knowledge_indexer)
    assert "create_index(" not in source
    assert "delete_index(" not in source


def test_indexer_script_never_logs_secrets(monkeypatch, capsys):
    search_secret = "super-secret-search-admin-key"
    storage_secret = "super-secret-storage-account-key"
    monkeypatch.setenv("AISEARCH_ENDPOINT", "https://fake.search.windows.net")
    monkeypatch.setenv("AISEARCH_APIKEY", search_secret)
    monkeypatch.setenv("AZURE_STORAGE_ACCOUNT_NAME", "seed123data")
    monkeypatch.setenv("AZURE_STORAGE_ACCOUNT_KEY", storage_secret)
    indexer_client = _FakeIndexerClient()
    monkeypatch.setattr(
        setup_knowledge_indexer,
        "_get_search_clients",
        lambda endpoint, api_key: (
            _FakeIndexClient(_compatible_index()),
            indexer_client,
        ),
    )

    setup_knowledge_indexer.run(apply_changes=True)

    captured = capsys.readouterr()
    assert search_secret not in captured.out
    assert storage_secret not in captured.out
