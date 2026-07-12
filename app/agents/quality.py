"""
Quality Agent — complexity and style. Same pattern as SecurityAgent:

    deterministic tool  ->  collect Findings  ->  optional LLM triage

The twist: this agent's triage is grounded by the RAG layer, which retrieves
the most relevant code chunks and coding-standards rules for the findings at
hand, so explanations cite the house rules instead of generic advice.
"""
from __future__ import annotations

from app.agents.base import Agent
from app.llm import triage_findings
from app.models import AgentReport, Finding
from app.rag import retrieve_context
from app.tools.complexity_checker import check_complexity


class QualityAgent(Agent):
    name = "quality"

    def review(self, codebase_path: str) -> AgentReport:
        try:
            findings: list[Finding] = check_complexity(codebase_path)
            context = ""
            if findings:
                query = " ".join(dict.fromkeys(
                    f"{f.rule} {f.title}" for f in findings))[:600]
                context = retrieve_context(codebase_path, query)
            findings = triage_findings(
                findings, role="senior code quality reviewer", context=context)
            return AgentReport(agent=self.name, findings=findings)
        except Exception as exc:  # a crashing agent must not sink the review
            return AgentReport(agent=self.name, error=str(exc))
