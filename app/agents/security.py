"""
Security Agent — the first specialist. Pattern for every future agent:

    deterministic tool(s)  ->  collect Findings  ->  optional LLM triage

Copy this file to build Quality / Test-Gap / Documentation agents; only the
tools in the middle change.
"""
from __future__ import annotations

from app.agents.base import Agent
from app.llm import triage_findings
from app.models import AgentReport, Finding
from app.tools.bandit_runner import run_bandit
from app.tools.secret_scanner import scan_secrets


class SecurityAgent(Agent):
    name = "security"

    def review(self, codebase_path: str) -> AgentReport:
        try:
            findings: list[Finding] = []
            findings += run_bandit(codebase_path)      # SAST
            findings += scan_secrets(codebase_path)    # secret detection
            findings = triage_findings(findings)       # LLM explains/ranks
            return AgentReport(agent=self.name, findings=findings)
        except Exception as exc:  # a crashing agent must not sink the review
            return AgentReport(agent=self.name, error=str(exc))
