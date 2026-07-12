"""
Test-Gap Agent — flags public API that the test suite never touches.
Same shape as every other specialist: deterministic tool, optional triage.
"""
from __future__ import annotations

from app.agents.base import Agent
from app.llm import triage_findings
from app.models import AgentReport
from app.tools.test_gap_checker import check_test_gaps


class TestGapAgent(Agent):
    name = "test-gap"

    def review(self, codebase_path: str) -> AgentReport:
        try:
            findings = check_test_gaps(codebase_path)
            findings = triage_findings(findings, role="senior test engineer")
            return AgentReport(agent=self.name, findings=findings)
        except Exception as exc:  # a crashing agent must not sink the review
            return AgentReport(agent=self.name, error=str(exc))
