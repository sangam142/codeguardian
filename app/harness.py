"""
Local CLI runner — the zero-setup entry point.

    python -m app.harness <path> [--no-history]

Runs the exact same run_review() pipeline the webhook uses, against a local
path, and prints the ranked Markdown report to stdout. No keys required.
Each run is also appended to the dashboard history unless --no-history.
"""
from __future__ import annotations

import sys

from app.history import record_review
from app.review import format_markdown, run_review


def main(argv: list[str] | None = None) -> int:
    # The report uses emoji; force UTF-8 so it prints on Windows consoles
    # (default cp1252) instead of raising UnicodeEncodeError.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    argv = list(sys.argv[1:] if argv is None else argv)
    no_history = "--no-history" in argv
    argv = [a for a in argv if a != "--no-history"]
    path = argv[0] if argv else "."

    report = run_review(path)
    print(format_markdown(report))
    if not no_history:
        record_review(report, source="harness", repo=path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
