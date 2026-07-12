"""
Deterministic layer for the Documentation Agent.

AST-based docstring coverage: missing module docstrings, missing docstrings
on public classes/functions, and a repo-level README check. Doc findings are
deliberately low-severity — they inform the health score without drowning
out real defects.
"""
from __future__ import annotations

import ast
from pathlib import Path

from app.models import Finding, Severity

_SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv"}
_MAX_FINDINGS = 25


def check_docs(path: str) -> list[Finding]:
    """Flag missing docstrings and README. Never raises."""
    root = Path(path)
    findings: list[Finding] = []
    if not root.exists():
        return findings

    if root.is_dir() and not any(root.glob("README*")):
        findings.append(Finding(
            agent="documentation", rule="DOC_NO_README", severity=Severity.LOW,
            title="Repository has no README", file=".", line=0,
            detail="A README is the first thing reviewers and new "
                   "contributors read."))

    files = [root] if root.is_file() else sorted(root.rglob("*.py"))
    for f in files:
        if not f.is_file() or f.suffix != ".py":
            continue
        if any(part in _SKIP_DIRS for part in f.parts):
            continue
        if f.name.startswith("test_") or f.stem.endswith("_test"):
            continue  # test names document themselves
        try:
            tree = ast.parse(f.read_text(errors="ignore"))
        except (SyntaxError, OSError):
            continue

        rel = _rel(f, root)
        if ast.get_docstring(tree) is None and f.name != "__init__.py":
            findings.append(Finding(
                agent="documentation", rule="DOC_NO_MODULE_DOC",
                severity=Severity.INFO,
                title=f"Module `{rel}` has no docstring", file=rel, line=1,
                detail="Open every module with one line saying what it's "
                       "for."))

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                     ast.ClassDef)):
                continue
            if node.name.startswith("_"):
                continue
            if ast.get_docstring(node) is not None:
                continue
            kind = "class" if isinstance(node, ast.ClassDef) else "function"
            findings.append(Finding(
                agent="documentation", rule="DOC_MISSING_DOCSTRING",
                severity=Severity.INFO,
                title=f"Public {kind} `{node.name}` has no docstring",
                file=rel, line=node.lineno,
                detail="Describe behavior and edge cases — especially what "
                       "happens on failure."))
            if len(findings) >= _MAX_FINDINGS:
                return findings
    return findings


def _rel(f: Path, root: Path) -> str:
    try:
        return f.relative_to(root).as_posix() if root.is_dir() else f.name
    except ValueError:
        return f.as_posix()
