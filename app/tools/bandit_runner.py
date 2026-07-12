"""
Deterministic layer #1: Bandit (Python security linter).

Bandit *finds* the issues; the LLM never invents vulnerabilities from
scratch — it only explains and prioritizes what a real tool reported.
That separation is the whole reason this design doesn't hallucinate.

Upgrade path: add Semgrep (multi-language) and Gitleaks (proper secret
scanning) as sibling runners once the Python slice works.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from app.models import Finding, Severity

# Bandit reports HIGH/MEDIUM/LOW; map to our scale.
_SEVERITY_MAP = {
    "HIGH": Severity.HIGH,
    "MEDIUM": Severity.MEDIUM,
    "LOW": Severity.LOW,
}


def run_bandit(path: str) -> list[Finding]:
    """Run bandit over a path and return structured findings. Never raises."""
    target = Path(path)
    if not target.exists():
        return []

    try:
        proc = subprocess.run(
            # Invoke via the current interpreter so it works even when the
            # `bandit` console script isn't on PATH (common on Windows).
            [sys.executable, "-m", "bandit", "-r", str(target),
             "-f", "json", "-q"],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        # Bandit not installed or too slow — degrade gracefully.
        return []

    # Bandit exits non-zero when it finds issues; that's expected, so we
    # parse stdout regardless of return code.
    if not proc.stdout.strip():
        return []

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return []

    findings: list[Finding] = []
    for r in data.get("results", []):
        sev = _SEVERITY_MAP.get(r.get("issue_severity", "LOW"), Severity.LOW)
        rel = _relativize(r.get("filename", ""), target)
        # B101 (assert used) is how tests are written; flagging every assert
        # in a test file is pure noise. Asserts in production code still count.
        if r.get("test_id") == "B101" and _is_test_file(rel):
            continue
        findings.append(
            Finding(
                agent="security",
                rule=r.get("test_id", "BANDIT"),
                severity=sev,
                title=r.get("issue_text", "Security issue"),
                file=rel,
                line=r.get("line_number", 0),
                detail=f"{r.get('test_name', '')} (confidence: "
                       f"{r.get('issue_confidence', '?')})",
            )
        )
    return findings


def _is_test_file(rel_path: str) -> bool:
    p = Path(rel_path)
    return (p.name.startswith("test_") or p.stem.endswith("_test")
            or any(part in ("tests", "test") for part in p.parts))


def _relativize(filename: str, root: Path) -> str:
    # Bandit returns paths relative to the CWD; resolve both to absolute so
    # the result is consistently relative to the codebase root.
    try:
        abs_file = Path(filename).resolve()
        abs_root = root.resolve()
        base = abs_root.parent if abs_root.is_file() else abs_root
        # Forward slashes render cleanly in the PR comment on any OS.
        return abs_file.relative_to(base).as_posix()
    except (ValueError, OSError):
        return filename
