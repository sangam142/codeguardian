"""
RAG layer — grounds the LLM triage step in the *actual* codebase.

At review time we index the code under review plus the project's
coding-standards doc, then retrieve the chunks most relevant to the current
findings and hand them to the LLM as context. Retrieval-only by design: the
LLM still never invents findings, it just explains them with better context.

Backend: ChromaDB (vector search) when installed; otherwise a dependency-free
keyword scorer. Same interface either way, so callers never care. Set
RAG_DISABLE=1 to skip retrieval entirely.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from app.config import settings

_SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv",
              "data", ".codeguardian"}
_INDEX_SUFFIXES = {".py", ".md", ".rst", ".txt"}
_CHUNK_LINES = 40
_MAX_FILES = 200
_MAX_CHUNKS = 800

# Path to this project's own standards doc; indexed alongside every review so
# the LLM can cite the house rules when explaining quality findings.
_STANDARDS_DOC = Path(__file__).resolve().parent.parent / "docs" / "coding_standards.md"


@dataclass
class Chunk:
    source: str      # "file.py:12" style label
    text: str


class RepoIndex:
    """Chunked index over a codebase. Build once per review, query many times."""

    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks
        self._collection = None  # chroma collection, if the backend loaded
        self._backend = "keyword"
        self._try_chroma()

    # ---------- construction ----------

    @classmethod
    def build(cls, codebase_path: str) -> "RepoIndex":
        chunks: list[Chunk] = []
        root = Path(codebase_path)
        files: list[Path] = []
        if root.is_file():
            files = [root]
        elif root.is_dir():
            files = sorted(
                f for f in root.rglob("*")
                if f.is_file() and f.suffix in _INDEX_SUFFIXES
                and not any(p in _SKIP_DIRS for p in f.parts)
            )[:_MAX_FILES]
        if _STANDARDS_DOC.exists():
            files.append(_STANDARDS_DOC)

        for f in files:
            try:
                text = f.read_text(errors="ignore")
            except OSError:
                continue
            label = f.name if f == _STANDARDS_DOC else _rel(f, root)
            lines = text.splitlines()
            for start in range(0, len(lines), _CHUNK_LINES):
                body = "\n".join(lines[start:start + _CHUNK_LINES]).strip()
                if body:
                    chunks.append(Chunk(f"{label}:{start + 1}", body))
                if len(chunks) >= _MAX_CHUNKS:
                    return cls(chunks)
        return cls(chunks)

    def _try_chroma(self) -> None:
        """Load chunks into an in-memory ChromaDB collection if possible.
        Any failure (not installed, embedding model unavailable) silently
        leaves the keyword backend in place."""
        if not self.chunks:
            return
        try:
            # This chromadb version's telemetry client is broken and logs an
            # error per event; disable it and mute its logger before import.
            import logging
            import os

            os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
            logging.getLogger("chromadb.telemetry").setLevel(logging.CRITICAL)
            import chromadb

            logging.getLogger("chromadb.telemetry.product.posthog").setLevel(
                logging.CRITICAL)
            client = chromadb.EphemeralClient(
                settings=chromadb.config.Settings(anonymized_telemetry=False))
            col = client.create_collection("codeguardian")
            col.add(
                ids=[str(i) for i in range(len(self.chunks))],
                documents=[c.text for c in self.chunks],
                metadatas=[{"source": c.source} for c in self.chunks],
            )
            self._collection = col
            self._backend = "chroma"
        except Exception:
            self._collection = None
            self._backend = "keyword"

    # ---------- retrieval ----------

    @property
    def backend(self) -> str:
        return self._backend

    def retrieve(self, query: str, k: int = 4) -> list[Chunk]:
        if not self.chunks or not query.strip():
            return []
        if self._collection is not None:
            try:
                res = self._collection.query(
                    query_texts=[query], n_results=min(k, len(self.chunks)))
                docs = res.get("documents", [[]])[0]
                metas = res.get("metadatas", [[]])[0]
                return [Chunk(m.get("source", "?"), d)
                        for d, m in zip(docs, metas)]
            except Exception:
                pass  # fall through to keyword scoring
        return self._keyword_retrieve(query, k)

    def _keyword_retrieve(self, query: str, k: int) -> list[Chunk]:
        q_tokens = set(_tokenize(query))
        if not q_tokens:
            return []
        scored = []
        for c in self.chunks:
            tokens = _tokenize(c.text)
            if not tokens:
                continue
            overlap = sum(1 for t in tokens if t in q_tokens)
            scored.append((overlap / len(tokens) ** 0.5, c))
        scored.sort(key=lambda s: -s[0])
        return [c for score, c in scored[:k] if score > 0]


def _tokenize(text: str) -> list[str]:
    # No underscore in the class: snake_case identifiers split into words so
    # code chunks match plain-English queries.
    return [t.lower() for t in re.findall(r"[A-Za-z]{3,}", text)]


def _rel(f: Path, root: Path) -> str:
    try:
        return f.relative_to(root).as_posix() if root.is_dir() else f.name
    except ValueError:
        return f.as_posix()


# One index per codebase path, reused across agents within a process.
_CACHE: dict[str, RepoIndex] = {}


def retrieve_context(codebase_path: str, query: str, k: int = 4) -> str:
    """Return a formatted context block for the LLM, or "" when RAG is off,
    empty, or anything fails. Never raises."""
    if settings.rag_disabled:
        return ""
    try:
        key = str(Path(codebase_path).resolve())
        index = _CACHE.get(key)
        if index is None:
            index = RepoIndex.build(codebase_path)
            _CACHE[key] = index
        chunks = index.retrieve(query, k=k)
        if not chunks:
            return ""
        return "\n\n".join(f"[{c.source}]\n{c.text}" for c in chunks)
    except Exception:
        return ""
