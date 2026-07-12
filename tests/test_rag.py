"""RAG layer: chunking and keyword retrieval (chroma is exercised only when
its embedding model is available, so tests pin the keyword backend)."""
from __future__ import annotations

import pytest

from app.config import settings
from app.rag import RepoIndex, retrieve_context


@pytest.fixture(autouse=True)
def _keyword_backend(monkeypatch):
    # Deterministic + offline: skip the chroma attempt entirely.
    monkeypatch.setattr(RepoIndex, "_try_chroma", lambda self: None)
    monkeypatch.setattr(settings, "rag_disabled", False)


def test_build_chunks_and_labels(tmp_path):
    (tmp_path / "mod.py").write_text("def unusual_token_xyz():\n    return 1\n")
    index = RepoIndex.build(str(tmp_path))
    assert index.backend == "keyword"
    assert any(c.source.startswith("mod.py:") for c in index.chunks)


def test_keyword_retrieval_ranks_relevant_chunk_first(tmp_path):
    (tmp_path / "a.py").write_text("def mutable_default_argument():\n    pass\n")
    (tmp_path / "b.py").write_text("def unrelated():\n    pass\n")
    index = RepoIndex.build(str(tmp_path))
    hits = index.retrieve("mutable default argument", k=1)
    assert hits and hits[0].source.startswith("a.py")


def test_standards_doc_is_indexed(tmp_path):
    (tmp_path / "x.py").write_text("pass\n")
    index = RepoIndex.build(str(tmp_path))
    assert any(c.source.startswith("coding_standards.md") for c in index.chunks)


def test_retrieve_context_disabled_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "rag_disabled", True)
    (tmp_path / "x.py").write_text("def f():\n    pass\n")
    assert retrieve_context(str(tmp_path), "anything") == ""
