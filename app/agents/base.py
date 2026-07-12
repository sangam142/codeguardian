"""
Base class every specialist agent inherits from.

An agent is deliberately tiny: it has a `name` and a `review(path)` method
that returns an `AgentReport`. The supervisor treats all agents uniformly, so
adding a specialist means subclassing this and implementing `review` — nothing
in the graph changes.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.models import AgentReport


class Agent(ABC):
    #: short identifier used in Findings and reports, e.g. "security".
    name: str = "agent"

    @abstractmethod
    def review(self, codebase_path: str) -> AgentReport:
        """Analyze the codebase at `codebase_path` and return findings.

        Implementations must never raise: catch internal errors and return an
        AgentReport with `error` set, so one failing agent can't sink the whole
        review.
        """
        raise NotImplementedError
