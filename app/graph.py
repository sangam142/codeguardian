"""
The multi-agent graph, built with LangGraph.

    [supervisor]  -> classify code, pick specialists
         |
    [specialists] -> run each selected agent, collect AgentReports
         |
    [aggregate]   -> assemble the single ReviewReport

This is deliberately minimal (3 nodes). It's the real orchestration pattern,
so adding agents = adding entries in supervisor.select_agents(), not rewiring
the graph. Swap the sequential loop for parallel execution when you need speed.
"""
from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents.base import Agent
from app.agents.supervisor import classify, select_agents
from app.models import AgentReport, ReviewReport


class ReviewState(TypedDict, total=False):
    codebase_path: str
    file_census: dict[str, int]
    agents: list[Agent]
    agent_reports: list[AgentReport]
    report: ReviewReport


def _supervisor_node(state: ReviewState) -> ReviewState:
    census = classify(state["codebase_path"])
    return {"file_census": census, "agents": select_agents(census)}


def _specialists_node(state: ReviewState) -> ReviewState:
    reports = [agent.review(state["codebase_path"]) for agent in state["agents"]]
    return {"agent_reports": reports}


def _aggregate_node(state: ReviewState) -> ReviewState:
    report = ReviewReport(
        codebase=state["codebase_path"],
        agent_reports=state.get("agent_reports", []),
    )
    return {"report": report}


def build_graph():
    g = StateGraph(ReviewState)
    g.add_node("supervisor", _supervisor_node)
    g.add_node("specialists", _specialists_node)
    g.add_node("aggregate", _aggregate_node)
    g.add_edge(START, "supervisor")
    g.add_edge("supervisor", "specialists")
    g.add_edge("specialists", "aggregate")
    g.add_edge("aggregate", END)
    return g.compile()


# Compile once at import; reuse across requests.
GRAPH = build_graph()
