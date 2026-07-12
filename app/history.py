"""
Review history — the dashboard's data source.

Every review (webhook or local harness) is appended to a small SQLite
database: timestamp, health score, and finding counts by severity and by
agent. SQLite is stdlib, needs no server, and one file survives restarts —
exactly enough persistence to chart health over time.

Relative CODEGUARDIAN_DB paths resolve against the project root so the
uvicorn server and `python -m app.harness` write to the same file no matter
which directory they were launched from.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings
from app.models import ReviewReport, Severity

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

_SCHEMA = """
CREATE TABLE IF NOT EXISTS reviews (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at    TEXT    NOT NULL,
    source        TEXT    NOT NULL,          -- 'webhook' | 'harness' | 'api'
    repo          TEXT,                      -- owner/name or local path
    pr_number     INTEGER,
    health_score  INTEGER NOT NULL,
    total         INTEGER NOT NULL,
    critical      INTEGER NOT NULL DEFAULT 0,
    high          INTEGER NOT NULL DEFAULT 0,
    medium        INTEGER NOT NULL DEFAULT 0,
    low           INTEGER NOT NULL DEFAULT 0,
    info          INTEGER NOT NULL DEFAULT 0,
    agents_json   TEXT    NOT NULL DEFAULT '{}'
)
"""


def _db_path() -> Path:
    p = Path(settings.db_path)
    if not p.is_absolute():
        p = _PROJECT_ROOT / p
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute(_SCHEMA)
    return conn


def record_review(report: ReviewReport, source: str,
                  repo: str | None = None,
                  pr_number: int | None = None) -> int | None:
    """Append one review to the history. Returns the row id, or None on
    failure — persistence must never break a review."""
    findings = report.all_findings
    by_sev = {s: 0 for s in Severity}
    by_agent: dict[str, int] = {}
    for f in findings:
        by_sev[f.severity] += 1
        by_agent[f.agent] = by_agent.get(f.agent, 0) + 1

    try:
        with _connect() as conn:
            cur = conn.execute(
                "INSERT INTO reviews (created_at, source, repo, pr_number, "
                "health_score, total, critical, high, medium, low, info, "
                "agents_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (datetime.now(timezone.utc).isoformat(timespec="seconds"),
                 source, repo or report.codebase, pr_number,
                 report.health_score, len(findings),
                 by_sev[Severity.CRITICAL], by_sev[Severity.HIGH],
                 by_sev[Severity.MEDIUM], by_sev[Severity.LOW],
                 by_sev[Severity.INFO], json.dumps(by_agent)))
            return cur.lastrowid
    except sqlite3.Error:
        return None


def fetch_reviews(limit: int = 100) -> list[dict]:
    """Most recent `limit` reviews, oldest first (chart-ready). Never raises."""
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT * FROM (SELECT * FROM reviews ORDER BY id DESC "
                "LIMIT ?) ORDER BY id ASC", (max(1, limit),)).fetchall()
    except sqlite3.Error:
        return []
    out = []
    for r in rows:
        d = dict(r)
        d["agents"] = json.loads(d.pop("agents_json") or "{}")
        out.append(d)
    return out


def summary() -> dict:
    """Headline numbers for the dashboard hero. Never raises."""
    try:
        with _connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS reviews, COALESCE(SUM(total),0) AS findings "
                "FROM reviews").fetchone()
            latest = conn.execute(
                "SELECT health_score FROM reviews ORDER BY id DESC LIMIT 1"
            ).fetchone()
    except sqlite3.Error:
        return {"reviews": 0, "findings": 0, "latest_health": None}
    return {"reviews": row["reviews"], "findings": row["findings"],
            "latest_health": latest["health_score"] if latest else None}
