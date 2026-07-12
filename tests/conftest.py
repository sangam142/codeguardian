"""
Shared test setup: force deterministic-only mode so the suite never touches
the network (no LLM calls, no ChromaDB embedding downloads) and never writes
to the real history database.
"""
from __future__ import annotations

import pytest

from app.config import settings


@pytest.fixture(autouse=True)
def _deterministic_settings(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "llm_api_key", None)
    monkeypatch.setattr(settings, "rag_disabled", True)
    monkeypatch.setattr(settings, "github_token", None)
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "history.db"))
    yield
