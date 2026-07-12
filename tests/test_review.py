"""End-to-end pipeline: run_review over a fixture tree, format the report."""
from __future__ import annotations

from app.review import format_markdown, run_review


def test_run_review_finds_planted_issues(tmp_path):
    (tmp_path / "app.py").write_text(
        'PASSWORD = "super-secret-hunter2"\n'
        "def f(x=[]):\n"
        "    return x\n"
    )
    report = run_review(str(tmp_path))

    agents = {r.agent for r in report.agent_reports}
    assert agents == {"security", "quality", "test-gap", "documentation"}
    assert not any(r.error for r in report.agent_reports)

    rules = {f.rule for f in report.all_findings}
    assert "SECRET_GENERIC" in rules          # security
    assert "QUAL_MUTABLE_DEFAULT" in rules    # quality
    assert "TEST_NO_TESTS" in rules           # test-gap
    assert "DOC_NO_README" in rules           # documentation
    assert report.health_score < 100


def test_format_markdown_contains_score_and_table(tmp_path):
    (tmp_path / "ok.py").write_text('"""doc."""\n\nX = 1\n')
    report = run_review(str(tmp_path))
    md = format_markdown(report)
    assert "CodeGuardian Review" in md
    assert f"Code-health score: {report.health_score}/100" in md
