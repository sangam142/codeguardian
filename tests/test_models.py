"""Health-score math and report ordering."""
from __future__ import annotations

from app.models import AgentReport, Finding, ReviewReport, Severity


def _finding(sev: Severity, file: str = "a.py", line: int = 1) -> Finding:
    return Finding(agent="security", rule="X", severity=sev, title="t",
                   file=file, line=line)


def test_health_score_perfect_when_clean():
    report = ReviewReport(codebase=".", agent_reports=[AgentReport(agent="s")])
    assert report.health_score == 100


def test_health_score_weights():
    report = ReviewReport(codebase=".", agent_reports=[AgentReport(
        agent="s", findings=[_finding(Severity.CRITICAL),   # -25
                             _finding(Severity.HIGH),       # -10
                             _finding(Severity.MEDIUM),     # -4
                             _finding(Severity.LOW),        # -1
                             _finding(Severity.INFO)])])    # -0
    assert report.health_score == 60


def test_health_score_floors_at_zero():
    findings = [_finding(Severity.CRITICAL) for _ in range(10)]
    report = ReviewReport(codebase=".", agent_reports=[
        AgentReport(agent="s", findings=findings)])
    assert report.health_score == 0


def test_all_findings_sorted_worst_first():
    report = ReviewReport(codebase=".", agent_reports=[
        AgentReport(agent="s", findings=[_finding(Severity.LOW, "b.py", 5),
                                         _finding(Severity.CRITICAL, "z.py", 9),
                                         _finding(Severity.LOW, "a.py", 2)])])
    ordered = report.all_findings
    assert [f.severity for f in ordered] == [Severity.CRITICAL, Severity.LOW,
                                             Severity.LOW]
    # ties break by file/line for stable output
    assert [f.file for f in ordered[1:]] == ["a.py", "b.py"]
