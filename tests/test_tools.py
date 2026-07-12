"""Deterministic tools against small fixture trees in tmp_path."""
from __future__ import annotations

from pathlib import Path

from app.models import Severity
from app.tools.bandit_runner import _is_test_file
from app.tools.complexity_checker import check_complexity
from app.tools.doc_checker import check_docs
from app.tools.secret_scanner import scan_secrets
from app.tools.test_gap_checker import check_test_gaps


def _write(root: Path, name: str, text: str) -> Path:
    p = root / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p


# ---------- complexity checker ----------

def test_complexity_flags_mutable_default_and_bare_except(tmp_path):
    _write(tmp_path, "m.py", (
        '"""doc."""\n'
        "def f(x=[]):\n"
        '    """doc."""\n'
        "    try:\n"
        "        return x\n"
        "    except:\n"
        "        pass\n"
    ))
    rules = {f.rule for f in check_complexity(str(tmp_path))}
    assert "QUAL_MUTABLE_DEFAULT" in rules
    assert "QUAL_BARE_EXCEPT" in rules


def test_complexity_flags_branchy_function(tmp_path):
    branches = "\n".join(f"    if x == {i}:\n        x += 1" for i in range(12))
    _write(tmp_path, "c.py", f'"""doc."""\ndef f(x):\n    """doc."""\n{branches}\n    return x\n')
    findings = check_complexity(str(tmp_path))
    assert any(f.rule == "QUAL_COMPLEXITY" for f in findings)


def test_complexity_clean_file_is_quiet(tmp_path):
    _write(tmp_path, "ok.py", '"""doc."""\ndef f(x):\n    """doc."""\n    return x + 1\n')
    assert check_complexity(str(tmp_path)) == []


def test_complexity_reports_syntax_error(tmp_path):
    _write(tmp_path, "bad.py", "def broken(:\n")
    findings = check_complexity(str(tmp_path))
    assert [f.rule for f in findings] == ["QUAL_SYNTAX_ERROR"]


# ---------- bandit runner ----------

def test_bandit_test_file_detection():
    # B101 (assert used) is exempt in test files but not production code.
    assert _is_test_file("tests/test_mod.py")
    assert _is_test_file("test_mod.py")
    assert _is_test_file("pkg/mod_test.py")
    assert not _is_test_file("app/mod.py")


# ---------- secret scanner ----------

def test_secret_scanner_finds_aws_key(tmp_path):
    _write(tmp_path, "cfg.py", 'KEY = "AKIAIOSFODNN7EXAMPLE"\n')
    findings = scan_secrets(str(tmp_path))
    assert any(f.rule == "SECRET_AWS_KEY" for f in findings)
    assert all(f.severity == Severity.CRITICAL for f in findings)


# ---------- test-gap checker ----------

def test_gap_flags_missing_suite(tmp_path):
    _write(tmp_path, "mod.py", "def api():\n    return 1\n")
    findings = check_test_gaps(str(tmp_path))
    assert [f.rule for f in findings] == ["TEST_NO_TESTS"]


def test_gap_flags_untested_function(tmp_path):
    _write(tmp_path, "mod.py", "def tested():\n    return 1\n\ndef orphan():\n    return 2\n")
    _write(tmp_path, "test_mod.py", "from mod import tested\n\ndef test_tested():\n    assert tested() == 1\n")
    findings = check_test_gaps(str(tmp_path))
    assert [f.title for f in findings] == ["No test references function `orphan`"]


def test_gap_private_names_ignored(tmp_path):
    _write(tmp_path, "mod.py", "def _internal():\n    return 1\n")
    _write(tmp_path, "test_mod.py", "def test_nothing():\n    assert True\n")
    assert check_test_gaps(str(tmp_path)) == []


# ---------- doc checker ----------

def test_doc_checker_flags_missing_docstrings_and_readme(tmp_path):
    _write(tmp_path, "mod.py", "def api():\n    return 1\n")
    rules = {f.rule for f in check_docs(str(tmp_path))}
    assert rules == {"DOC_NO_README", "DOC_NO_MODULE_DOC", "DOC_MISSING_DOCSTRING"}


def test_doc_checker_quiet_when_documented(tmp_path):
    _write(tmp_path, "README.md", "# proj\n")
    _write(tmp_path, "mod.py", '"""Module doc."""\n\ndef api():\n    """Doc."""\n    return 1\n')
    assert check_docs(str(tmp_path)) == []
