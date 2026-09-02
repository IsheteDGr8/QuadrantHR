"""Tests for document-editor workspace path resolution."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

# Import helpers from the marketplace server module.
import importlib.util

_SERVER_PATH = (
    Path(__file__).resolve().parents[1]
    / "marketplaces"
    / "integrations"
    / "document-editor"
    / "server"
    / "document_server.py"
)


def _load_document_server():
    spec = importlib.util.spec_from_file_location("document_server", _SERVER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def doc_server(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "i9_form.pdf").write_bytes(b"%PDF-1.4 test")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HRAGENT_WORKSPACE_DIR", str(workspace))
    return _load_document_server()


def test_resolve_existing_input(doc_server):
    resolved = doc_server._resolve_path("i9_form.pdf")
    assert resolved.name == "i9_form.pdf"
    assert resolved.exists()


def test_resolve_output_before_exists(doc_server):
    resolved = doc_server._resolve_path("outputs/new_form.pdf", must_exist=False)
    assert resolved.parent.name == "outputs"
    assert str(resolved).endswith("workspace\\outputs\\new_form.pdf") or str(
        resolved
    ).endswith("workspace/outputs/new_form.pdf")


def test_output_not_written_to_repo_root(doc_server, tmp_path):
    out = doc_server._resolve_path("filled.pdf", must_exist=False)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(b"filled")
    assert out.is_relative_to(tmp_path / "workspace")
    assert not out.is_relative_to(tmp_path) or out.parts[-2] == "workspace"
