"""Supervisor routing: which specialists run for which file mix."""
from __future__ import annotations

from app.agents.supervisor import classify, select_agents


def _names(census: dict[str, int]) -> list[str]:
    return [a.name for a in select_agents(census)]


def test_python_codebase_gets_all_agents():
    assert _names({".py": 3}) == ["security", "quality", "test-gap",
                                  "documentation"]


def test_docs_only_change_gets_documentation_only():
    assert _names({".md": 2}) == ["documentation"]


def test_js_codebase_gets_security_only():
    assert _names({".js": 4}) == ["security"]


def test_no_relevant_files_no_agents():
    assert _names({".png": 1}) == []


def test_classify_counts_by_suffix(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n")
    (tmp_path / "b.py").write_text("y = 2\n")
    (tmp_path / "README.md").write_text("# hi\n")
    census = classify(str(tmp_path))
    assert census == {".py": 2, ".md": 1}
