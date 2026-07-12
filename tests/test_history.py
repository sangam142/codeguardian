"""History persistence round-trip (against a temp DB, see conftest)."""
from __future__ import annotations

from app.history import fetch_reviews, record_review, summary
from app.models import AgentReport, Finding, ReviewReport, Severity


def _report() -> ReviewReport:
    return ReviewReport(codebase="sample", agent_reports=[
        AgentReport(agent="security", findings=[
            Finding(agent="security", rule="B1", severity=Severity.HIGH,
                    title="t", file="a.py", line=1)]),
        AgentReport(agent="quality", findings=[
            Finding(agent="quality", rule="Q1", severity=Severity.LOW,
                    title="t", file="a.py", line=2)]),
    ])


def test_record_and_fetch_roundtrip():
    row_id = record_review(_report(), source="harness")
    assert row_id is not None

    rows = fetch_reviews()
    assert len(rows) == 1
    row = rows[0]
    assert row["source"] == "harness"
    assert row["repo"] == "sample"
    assert row["health_score"] == 89          # 100 - 10 - 1
    assert row["total"] == 2
    assert (row["high"], row["low"]) == (1, 1)
    assert row["agents"] == {"security": 1, "quality": 1}


def test_fetch_returns_oldest_first_and_respects_limit():
    for _ in range(5):
        record_review(_report(), source="harness")
    rows = fetch_reviews(limit=3)
    assert len(rows) == 3
    assert [r["id"] for r in rows] == sorted(r["id"] for r in rows)


def test_summary_counts():
    record_review(_report(), source="webhook", repo="o/r", pr_number=7)
    s = summary()
    assert s["reviews"] == 1
    assert s["findings"] == 2
    assert s["latest_health"] == 89
