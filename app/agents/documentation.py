"""
Documentation Agent — docstring coverage + README presence.
Same shape as every other specialist: deterministic tool, optional triage.
"""
from __future__ import annotations

from app.agents.base import Agent
from app.llm import triage_findings
from app.models import AgentReport
from app.tools.doc_checker import check_docs


class DocumentationAgent(Agent):
    name = "documentation"

    def review(self, codebase_path: str) -> AgentReport:
        try:
            findings = check_docs(codebase_path)
            findings = triage_findings(
                findings, role="technical documentation reviewer")
            return AgentReport(agent=self.name, findings=findings)
        except Exception as exc:  # a crashing agent must not sink the review
            return AgentReport(agent=self.name, error=str(exc))
