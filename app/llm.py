"""
Optional LLM layer. This NEVER creates findings — it only adds a plain-English
`explanation` and `fix_hint` to findings that a deterministic tool already
reported. If no LLM key is configured, everything still works; findings just
ship without the extra prose.

Uses an OpenAI-compatible client so it works with Groq (free), Ollama (local),
OpenAI, etc. — just point LLM_BASE_URL/LLM_MODEL at whatever you have.
"""
from __future__ import annotations

import json

from app.config import settings
from app.models import Finding


def triage_findings(findings: list[Finding],
                    role: str = "senior security reviewer",
                    context: str = "") -> list[Finding]:
    """Enrich findings with explanation + fix hint. Returns them unchanged
    if the LLM is unavailable or errors out.

    `role` tailors the persona per agent ("senior code quality reviewer", …).
    `context` is optional RAG-retrieved code/standards excerpts that ground
    the explanations in the actual codebase.
    """
    if not settings.llm_enabled or not findings:
        return findings

    try:
        from openai import OpenAI  # lazy import: not required to run
    except ImportError:
        return findings

    client = OpenAI(api_key=settings.llm_api_key,
                    base_url=settings.llm_base_url)

    payload = [
        {"i": i, "rule": f.rule, "title": f.title,
         "file": f.file, "line": f.line, "severity": f.severity.label}
        for i, f in enumerate(findings)
    ]
    context_block = (
        f"Relevant excerpts from the codebase and its coding standards:\n"
        f"{context}\n\n" if context else ""
    )
    prompt = (
        f"You are a {role}. For each finding below, write a "
        "one-sentence plain-English explanation of the risk and a one-sentence "
        "concrete fix. Do NOT invent new issues. Reply with ONLY a JSON array "
        "of objects like {\"i\": int, \"explanation\": str, \"fix\": str}.\n\n"
        f"{context_block}"
        f"Findings:\n{json.dumps(payload)}"
    )

    try:
        resp = client.chat.completions.create(
            model=settings.llm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        raw = resp.choices[0].message.content or ""
        raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```")
        enriched = {item["i"]: item for item in json.loads(raw)}
    except Exception:
        # Any failure (network, parse, rate limit) — keep deterministic output.
        return findings

    for i, f in enumerate(findings):
        if i in enriched:
            f.explanation = enriched[i].get("explanation", "")
            f.fix_hint = enriched[i].get("fix", "")
    return findings
