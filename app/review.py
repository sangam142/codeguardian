"""
One function everything funnels through: run_review(path) -> ReviewReport.
Both the local harness and the GitHub webhook call this, so there's exactly
one code path to test and reason about.
"""
from __future__ import annotations

from app.graph import GRAPH
from app.models import ReviewReport, Severity

_EMOJI = {
    Severity.CRITICAL: "🔴",
    Severity.HIGH: "🟠",
    Severity.MEDIUM: "🟡",
    Severity.LOW: "🔵",
    Severity.INFO: "⚪",
}


def run_review(codebase_path: str) -> ReviewReport:
    result = GRAPH.invoke({"codebase_path": codebase_path})
    return result["report"]


def format_markdown(report: ReviewReport) -> str:
    """Render the report as a Markdown PR comment."""
    findings = report.all_findings
    lines: list[str] = []
    lines.append("## 🛡️ CodeGuardian Review\n")
    lines.append(f"**Code-health score: {report.health_score}/100** · "
                 f"{len(findings)} finding(s)\n")

    # Note any agent that errored, so silent failures are visible.
    for r in report.agent_reports:
        if r.error:
            lines.append(f"> ⚠️ `{r.agent}` agent failed: {r.error}\n")

    if not findings:
        lines.append("✅ No issues found. Nice work.\n")
        return "\n".join(lines)

    # Severity summary
    counts: dict[Severity, int] = {}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1
    summary = " · ".join(
        f"{_EMOJI[s]} {counts[s]} {s.label}"
        for s in sorted(counts, reverse=True)
    )
    lines.append(summary + "\n")

    lines.append("| Sev | Issue | Location | Rule |")
    lines.append("|-----|-------|----------|------|")
    for f in findings:
        loc = f"`{f.file}:{f.line}`" if f.line else f"`{f.file}`"
        lines.append(f"| {_EMOJI[f.severity]} {f.severity.label} | "
                     f"{f.title} | {loc} | `{f.rule}` |")

    # Detailed explanations (LLM-enriched when available)
    lines.append("\n<details><summary>Details</summary>\n")
    for f in findings:
        lines.append(f"\n**{_EMOJI[f.severity]} {f.title}** "
                     f"(`{f.file}:{f.line}`, `{f.rule}`)")
        if f.detail:
            lines.append(f"- {f.detail}")
        if f.explanation:
            lines.append(f"- _Risk:_ {f.explanation}")
        if f.fix_hint:
            lines.append(f"- _Fix:_ {f.fix_hint}")
    lines.append("\n</details>")
    return "\n".join(lines)
