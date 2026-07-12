"""
Supervisor Agent — the brain of the fan-out. Right now it does simple,
explainable routing: if there's Python code, run the Security Agent. As you
add specialists, this is where you decide *which* agents each PR needs
(e.g. skip the Test-Gap agent on a docs-only change).
"""
from __future__ import annotations

from pathlib import Path

from app.agents.base import Agent
from app.agents.documentation import DocumentationAgent
from app.agents.quality import QualityAgent
from app.agents.security import SecurityAgent
from app.agents.test_gap import TestGapAgent

_SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv"}


def classify(codebase_path: str) -> dict[str, int]:
    """Cheap file-type census used for routing decisions."""
    counts: dict[str, int] = {}
    root = Path(codebase_path)
    if not root.exists():
        return counts
    for f in root.rglob("*"):
        if f.is_file() and not any(p in _SKIP_DIRS for p in f.parts):
            counts[f.suffix or "<none>"] = counts.get(f.suffix or "<none>", 0) + 1
    return counts


def select_agents(file_census: dict[str, int]) -> list[Agent]:
    """Decide which specialists to dispatch.

    Routing rules:
      - any code (.py/.js/.ts)  -> Security (secrets hide in every language)
      - Python code             -> Quality + Test-Gap (both are AST-based)
      - Python or Markdown      -> Documentation
    A docs-only change therefore skips the code agents entirely.
    """
    agents: list[Agent] = []
    has_code = any(ext in file_census for ext in (".py", ".js", ".ts"))
    has_python = ".py" in file_census
    if has_code:
        agents.append(SecurityAgent())
    if has_python:
        agents.append(QualityAgent())
        agents.append(TestGapAgent())
    if has_python or ".md" in file_census:
        agents.append(DocumentationAgent())
    return agents
