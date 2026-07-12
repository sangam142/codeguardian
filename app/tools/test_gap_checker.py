"""
Deterministic layer for the Test-Gap Agent.

Static heuristic, no execution: collect every public module-level function
and class in the source tree, collect every identifier mentioned anywhere in
the test files, and flag public API that no test ever references. Coarse by
design — it catches the "we never wrote a test for this" gap, not assertion
quality. Swap in coverage.py data later for precision; the Finding shape
stays the same.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

from app.models import Finding, Severity

_SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv"}
_MAX_FINDINGS = 15
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def check_test_gaps(path: str) -> list[Finding]:
    """Flag public functions/classes never referenced by any test. Never raises."""
    root = Path(path)
    if not root.exists():
        return []

    files = [root] if root.is_file() else sorted(root.rglob("*.py"))
    sources, tests = [], []
    for f in files:
        if not f.is_file() or f.suffix != ".py":
            continue
        if any(part in _SKIP_DIRS for part in f.parts):
            continue
        (tests if _is_test_file(f) else sources).append(f)

    if not sources:
        return []
    if not tests:
        return [Finding(
            agent="test-gap", rule="TEST_NO_TESTS", severity=Severity.MEDIUM,
            title="Codebase contains no test files",
            file=_rel(root, root), line=0,
            detail=f"{len(sources)} Python file(s) but no test_*.py / "
                   "*_test.py. Untested code regresses silently.")]

    tested_names: set[str] = set()
    for t in tests:
        try:
            tested_names.update(_IDENT.findall(t.read_text(errors="ignore")))
        except OSError:
            continue

    findings: list[Finding] = []
    for src in sources:
        for name, line, kind in _public_api(src):
            if name in tested_names:
                continue
            findings.append(Finding(
                agent="test-gap", rule="TEST_GAP", severity=Severity.LOW,
                title=f"No test references {kind} `{name}`",
                file=_rel(src, root), line=line,
                detail="Nothing in the test suite mentions this name; it has "
                       "no direct test."))
            if len(findings) >= _MAX_FINDINGS:
                return findings
    return findings


def _is_test_file(f: Path) -> bool:
    if f.name.startswith("test_") or f.stem.endswith("_test"):
        return True
    return any(part in ("tests", "test") for part in f.parts)


def _public_api(f: Path) -> list[tuple[str, int, str]]:
    """(name, line, kind) for public module-level defs. Empty on parse error."""
    try:
        tree = ast.parse(f.read_text(errors="ignore"))
    except (SyntaxError, OSError):
        return []
    out = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                out.append((node.name, node.lineno, "function"))
        elif isinstance(node, ast.ClassDef):
            if not node.name.startswith("_"):
                out.append((node.name, node.lineno, "class"))
    return out


def _rel(f: Path, root: Path) -> str:
    try:
        return f.relative_to(root).as_posix() if root.is_dir() else f.name
    except ValueError:
        return f.as_posix()
