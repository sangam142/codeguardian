"""
Central configuration. Every field is optional so the pipeline runs with
zero setup (deterministic-only mode). Add keys later to unlock LLM triage
and real GitHub posting.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

# Load a local .env into os.environ if present, so keys in .env "just work".
# Real environment variables always win over .env (override=False).
try:
    from dotenv import load_dotenv

    load_dotenv(override=False)
except ImportError:  # python-dotenv not installed — env vars still work.
    pass


def _get(name: str, default: str | None = None) -> str | None:
    val = os.environ.get(name, default)
    return val if val else default


@dataclass
class Settings:
    # --- GitHub (needed only for the live webhook / posting comments) ---
    github_webhook_secret: str | None = None
    github_token: str | None = None

    # --- LLM triage (optional). Groq is free + OpenAI-compatible. ---
    # Get a free key at https://console.groq.com and check its model list;
    # model names change, so we keep it configurable.
    llm_api_key: str | None = None
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_model: str = "llama-3.1-8b-instant"

    # --- RAG (Quality Agent context retrieval). On by default; set
    # RAG_DISABLE=1 to skip. Uses ChromaDB when installed, else a built-in
    # keyword scorer. ---
    rag_disabled: bool = False

    # --- Dashboard history DB. Relative paths resolve against the project
    # root so the server and the CLI harness share one database. ---
    db_path: str = "data/history.db"

    @classmethod
    def load(cls) -> "Settings":
        return cls(
            github_webhook_secret=_get("GITHUB_WEBHOOK_SECRET"),
            github_token=_get("GITHUB_TOKEN"),
            llm_api_key=_get("LLM_API_KEY"),
            llm_base_url=_get("LLM_BASE_URL", "https://api.groq.com/openai/v1"),
            llm_model=_get("LLM_MODEL", "llama-3.1-8b-instant"),
            rag_disabled=_get("RAG_DISABLE") in ("1", "true", "yes"),
            db_path=_get("CODEGUARDIAN_DB", "data/history.db"),
        )

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_api_key)


settings = Settings.load()
