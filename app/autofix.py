"""
Auto-fix — the stretch goal, always behind a human-approval gate.

    python -m app.autofix <path>            # propose fixes (writes nothing
                                            # outside .codeguardian/)
    python -m app.autofix <path> --apply    # apply after an interactive [y/N]
    python -m app.autofix <path> --apply --yes   # explicit non-interactive OK

Flow: run the normal review, ask the LLM for a minimal patch per finding,
then *validate* each proposal — the original snippet must match the file
exactly once — before it is even shown. Nothing touches the working tree
unless a human passes --apply and confirms. This tool never commits, never
pushes, never opens PRs: you review the diff and raise the PR yourself.

Requires an LLM key (see .env). Without one there is nothing safe to
propose, so it exits with a message instead of guessing.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from app.config import settings
from app.models import Finding, Severity
from app.review import run_review

_OUT_DIR = Path(".codeguardian")
_MAX_FIXES = 10
_SNIPPET_CONTEXT = 8  # lines around the finding shown to the LLM


def propose_fixes(codebase_path: str) -> list[dict]:
    """Review the path and return validated fix proposals:
    {file, line, rule, title, original, fixed, note}. Never raises."""
    report = run_review(codebase_path)
    findings = [f for f in report.all_findings
                if f.severity >= Severity.LOW and f.line > 0][:_MAX_FIXES]
    if not findings:
        return []

    root = Path(codebase_path).resolve()
    payload = []
    for i, f in enumerate(findings):
        snippet = _read_snippet(root, f)
        if snippet is None:
            continue
        payload.append({"i": i, "rule": f.rule, "title": f.title,
                        "file": f.file, "line": f.line, "snippet": snippet})
    if not payload:
        return []

    raw = _ask_llm(payload)
    if raw is None:
        return []

    proposals: list[dict] = []
    for item in raw:
        try:
            f = findings[item["i"]]
            original, fixed = item["original"], item["fixed"]
        except (KeyError, IndexError, TypeError):
            continue
        target = _safe_path(root, f.file)
        if target is None or not isinstance(original, str) \
                or not isinstance(fixed, str) or original == fixed:
            continue
        try:
            text = target.read_text(errors="ignore")
        except OSError:
            continue
        # The gate before the gate: only exact, unambiguous matches survive.
        if text.count(original) != 1:
            continue
        proposals.append({
            "file": f.file, "line": f.line, "rule": f.rule, "title": f.title,
            "original": original, "fixed": fixed,
            "note": str(item.get("note", "")),
        })
    return proposals


def apply_fixes(codebase_path: str, proposals: list[dict]) -> int:
    """Apply validated proposals to the working tree. Returns count applied."""
    root = Path(codebase_path).resolve()
    applied = 0
    for p in proposals:
        target = _safe_path(root, p["file"])
        if target is None:
            continue
        try:
            text = target.read_text(errors="ignore")
            if text.count(p["original"]) != 1:
                continue  # file changed since the proposal was made
            target.write_text(text.replace(p["original"], p["fixed"], 1))
            applied += 1
        except OSError:
            continue
    return applied


def _read_snippet(root: Path, f: Finding) -> str | None:
    target = _safe_path(root, f.file)
    if target is None:
        return None
    try:
        lines = target.read_text(errors="ignore").splitlines()
    except OSError:
        return None
    lo = max(0, f.line - 1 - _SNIPPET_CONTEXT)
    hi = min(len(lines), f.line + _SNIPPET_CONTEXT)
    return "\n".join(lines[lo:hi])


def _safe_path(root: Path, rel: str) -> Path | None:
    """Resolve `rel` under `root`; refuse anything that escapes it."""
    base = root.parent if root.is_file() else root
    try:
        p = (base / rel).resolve()
        p.relative_to(base)
    except (ValueError, OSError):
        return None
    return p if p.is_file() else None


def _ask_llm(payload: list[dict]) -> list[dict] | None:
    try:
        from openai import OpenAI
    except ImportError:
        return None
    client = OpenAI(api_key=settings.llm_api_key,
                    base_url=settings.llm_base_url)
    prompt = (
        "You are a careful code-fixing assistant. For each finding, propose "
        "the smallest safe fix. Reply with ONLY a JSON array of objects: "
        '{"i": int, "original": str, "fixed": str, "note": str}. '
        "`original` MUST be copied verbatim from the snippet (it is used for "
        "exact string replacement) and `fixed` is its replacement. Skip any "
        "finding you cannot fix minimally and safely.\n\n"
        f"Findings with code snippets:\n{json.dumps(payload)}"
    )
    try:
        resp = client.chat.completions.create(
            model=settings.llm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        raw = (resp.choices[0].message.content or "").strip()
        raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```")
        data = json.loads(raw)
        return data if isinstance(data, list) else None
    except Exception:
        return None


def _write_reports(proposals: list[dict]) -> None:
    _OUT_DIR.mkdir(exist_ok=True)
    (_OUT_DIR / "fixes.json").write_text(json.dumps(proposals, indent=2))
    lines = ["# CodeGuardian proposed fixes\n"]
    for i, p in enumerate(proposals, 1):
        lines += [f"## {i}. {p['title']} (`{p['file']}:{p['line']}`, "
                  f"`{p['rule']}`)",
                  f"{p['note']}\n" if p["note"] else "",
                  "```diff",
                  *("- " + ln for ln in p["original"].splitlines()),
                  *("+ " + ln for ln in p["fixed"].splitlines()),
                  "```\n"]
    (_OUT_DIR / "fixes.md").write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    argv = list(sys.argv[1:] if argv is None else argv)
    apply_mode = "--apply" in argv
    assume_yes = "--yes" in argv
    args = [a for a in argv if not a.startswith("--")]
    path = args[0] if args else "."

    if not settings.llm_enabled:
        print("Auto-fix needs an LLM (set LLM_API_KEY in .env). Deterministic "
              "tools can find issues, but guessing fixes without a model "
              "isn't safe.")
        return 1

    print(f"Reviewing {path} and drafting fixes...")
    proposals = propose_fixes(path)
    if not proposals:
        print("No safely-fixable findings (or the LLM returned nothing "
              "usable). Nothing was changed.")
        return 0

    _write_reports(proposals)
    print(f"\n{len(proposals)} validated fix proposal(s) written to "
          f"{_OUT_DIR / 'fixes.md'}:\n")
    for i, p in enumerate(proposals, 1):
        print(f"  {i}. [{p['rule']}] {p['file']}:{p['line']} — {p['title']}")

    if not apply_mode:
        print("\nReview the proposals, then re-run with --apply to use them. "
              "Nothing has been modified.")
        return 0

    if not assume_yes:
        answer = input(f"\nApply {len(proposals)} fix(es) to {path}? [y/N] ")
        if answer.strip().lower() not in ("y", "yes"):
            print("Aborted. Nothing was modified.")
            return 0

    applied = apply_fixes(path, proposals)
    print(f"Applied {applied}/{len(proposals)} fix(es). Review the diff and "
          "open the PR yourself — CodeGuardian never pushes code.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
