"""
Deterministic layer #2: a tiny secret scanner.

This is a lightweight stand-in for Gitleaks so the first slice has zero
extra binary dependencies. Swap in real Gitleaks later for far better
coverage — the Finding shape stays identical, so nothing downstream changes.
"""
from __future__ import annotations

import re
from pathlib import Path

from app.models import Finding, Severity

# (rule_id, human title, compiled pattern)
_PATTERNS: list[tuple[str, str, re.Pattern]] = [
    ("SECRET_AWS_KEY", "Hard-coded AWS access key",
     re.compile(r"AKIA[0-9A-Z]{16}")),
    ("SECRET_PRIVATE_KEY", "Committed private key block",
     re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("SECRET_GENERIC", "Possible hard-coded credential",
     re.compile(r"(?i)(password|passwd|secret|api[_-]?key|token)\s*[=:]\s*"
                r"['\"][^'\"]{6,}['\"]")),
]

_SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv"}
_TEXT_SUFFIXES = {".py", ".js", ".ts", ".java", ".go", ".rb", ".env",
                  ".yml", ".yaml", ".json", ".txt", ".cfg", ".ini", ".sh"}


def scan_secrets(path: str) -> list[Finding]:
    """Walk text files under `path` and flag likely secrets. Never raises."""
    root = Path(path)
    findings: list[Finding] = []
    if not root.exists():
        return findings

    files = [root] if root.is_file() else root.rglob("*")
    for f in files:
        if not f.is_file():
            continue
        if any(part in _SKIP_DIRS for part in f.parts):
            continue
        if f.suffix and f.suffix not in _TEXT_SUFFIXES:
            continue
        try:
            text = f.read_text(errors="ignore")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), start=1):
            for rule, title, pat in _PATTERNS:
                if pat.search(line):
                    findings.append(
                        Finding(
                            agent="security",
                            rule=rule,
                            severity=Severity.CRITICAL,
                            title=title,
                            file=_rel(f, root),
                            line=i,
                            detail="Secrets must live in a vault or env "
                                   "vars, never in source.",
                        )
                    )
    return findings


def _rel(f: Path, root: Path) -> str:
    # Use forward slashes so paths render cleanly in the PR comment on any OS.
    try:
        return f.relative_to(root).as_posix() if root.is_dir() else f.name
    except ValueError:
        return f.as_posix()
