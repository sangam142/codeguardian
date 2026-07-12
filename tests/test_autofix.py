"""Auto-fix safety rails: path containment and exact-match application."""
from __future__ import annotations

from pathlib import Path

from app.autofix import _safe_path, apply_fixes


def test_safe_path_rejects_escape(tmp_path):
    (tmp_path / "inside.py").write_text("x = 1\n")
    assert _safe_path(tmp_path, "inside.py") is not None
    assert _safe_path(tmp_path, "../outside.py") is None
    assert _safe_path(tmp_path, "missing.py") is None


def test_apply_fixes_replaces_exact_match(tmp_path):
    target = tmp_path / "m.py"
    target.write_text("def f(x=[]):\n    return x\n")
    applied = apply_fixes(str(tmp_path), [{
        "file": "m.py", "line": 1, "rule": "QUAL_MUTABLE_DEFAULT", "title": "t",
        "original": "def f(x=[]):", "fixed": "def f(x=None):",
        "note": "",
    }])
    assert applied == 1
    assert "x=None" in target.read_text()


def test_apply_fixes_skips_stale_or_ambiguous(tmp_path):
    target = tmp_path / "m.py"
    target.write_text("a = 1\na = 1\n")  # ambiguous: two matches
    applied = apply_fixes(str(tmp_path), [{
        "file": "m.py", "line": 1, "rule": "R", "title": "t",
        "original": "a = 1", "fixed": "a = 2", "note": "",
    }])
    assert applied == 0
    assert target.read_text() == "a = 1\na = 1\n"
