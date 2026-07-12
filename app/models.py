"""
Shared data structures. Every agent speaks in `Finding`s; the supervisor
aggregates them into a single `ReviewReport`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum


class Severity(IntEnum):
    """Higher = worse. Used for sorting the final report."""
    INFO = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

    @property
    def label(self) -> str:
        return self.name.title()


@dataclass
class Finding:
    agent: str            # which specialist produced this ("security", ...)
    rule: str             # tool rule id, e.g. "B602" or "SECRET_AWS_KEY"
    severity: Severity
    title: str            # short human summary
    file: str             # relative path
    line: int             # 1-based line number (0 if unknown)
    detail: str = ""      # deterministic tool detail
    explanation: str = "" # filled in by the LLM triage step (optional)
    fix_hint: str = ""    # suggested remediation (optional)


@dataclass
class AgentReport:
    agent: str
    findings: list[Finding] = field(default_factory=list)
    error: str | None = None  # set if the agent crashed, so one failure
                              # never sinks the whole review


@dataclass
class ReviewReport:
    codebase: str
    agent_reports: list[AgentReport] = field(default_factory=list)

    @property
    def all_findings(self) -> list[Finding]:
        out: list[Finding] = []
        for r in self.agent_reports:
            out.extend(r.findings)
        # worst first, then by file/line for stable ordering
        return sorted(out, key=lambda f: (-int(f.severity), f.file, f.line))

    @property
    def health_score(self) -> int:
        """
        Simple 0-100 code-health score. Deterministic and explainable —
        the kind of metric you can chart over time on the dashboard.
        """
        weights = {
            Severity.CRITICAL: 25,
            Severity.HIGH: 10,
            Severity.MEDIUM: 4,
            Severity.LOW: 1,
            Severity.INFO: 0,
        }
        penalty = sum(weights[f.severity] for f in self.all_findings)
        return max(0, 100 - penalty)
