"""
FastAPI webhook receiver — the live-app entry point.

    uvicorn app.main:app --reload

GitHub sends a PR event -> we verify the signature -> check out the PR head ->
run the same run_review() pipeline the harness uses -> post the report as a
PR comment.

The PR head is shallow-cloned into a temp dir (see pr_checkout), so the review
runs against the real PR code. If the clone fails it degrades to reviewing the
server's cwd rather than crashing.
"""
from __future__ import annotations

import hashlib
import hmac
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel

from app.config import settings
from app.github_client import post_pr_comment
from app.history import fetch_reviews, record_review, summary
from app.pr_checkout import checkout_pr_head
from app.review import format_markdown, run_review

app = FastAPI(title="CodeGuardian AI")

_STATIC = Path(__file__).resolve().parent / "static"


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# ---------- dashboard ----------

@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse("/dashboard")


@app.get("/dashboard", include_in_schema=False)
def dashboard() -> FileResponse:
    return FileResponse(_STATIC / "dashboard.html", media_type="text/html")


@app.get("/api/history")
def api_history(limit: int = 100) -> dict:
    """Recent reviews, oldest first — feeds the dashboard charts."""
    return {"reviews": fetch_reviews(limit)}


@app.get("/api/summary")
def api_summary() -> dict:
    """Headline numbers for the dashboard hero cards."""
    return summary()


class ScanRequest(BaseModel):
    path: str = "sample_vulnerable_code"


@app.post("/api/scan")
def api_scan(req: ScanRequest) -> dict:
    """Run a review of a local path and record it — the dashboard's demo
    button. Local-dev convenience; don't expose this server publicly with
    it enabled."""
    report = run_review(req.path)
    record_review(report, source="api", repo=req.path)
    return {
        "path": req.path,
        "health_score": report.health_score,
        "findings": len(report.all_findings),
    }


def _verify_signature(body: bytes, signature: str | None) -> bool:
    """Validate GitHub's HMAC-SHA256 signature. If no secret is configured,
    skip verification (dev mode) but warn."""
    if not settings.github_webhook_secret:
        return True  # dev mode
    if not signature:
        return False
    mac = hmac.new(
        settings.github_webhook_secret.encode(),
        msg=body,
        digestmod=hashlib.sha256,
    )
    expected = "sha256=" + mac.hexdigest()
    return hmac.compare_digest(expected, signature)


@app.post("/webhook")
async def webhook(
    request: Request,
    x_github_event: str = Header(default=""),
    x_hub_signature_256: str | None = Header(default=None),
) -> dict:
    body = await request.body()
    if not _verify_signature(body, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Bad signature")

    if x_github_event != "pull_request":
        return {"skipped": f"event '{x_github_event}' ignored"}

    payload = await request.json()
    if payload.get("action") not in {"opened", "synchronize", "reopened"}:
        return {"skipped": payload.get("action")}

    repo = payload["repository"]["full_name"]
    pr_number = payload["number"]

    # Clone the PR head into a temp dir and review that real code.
    with checkout_pr_head(payload) as codebase_path:
        report = run_review(codebase_path)

    record_review(report, source="webhook", repo=repo, pr_number=pr_number)
    comment = format_markdown(report)
    posted = post_pr_comment(repo, pr_number, comment)

    return {
        "repo": repo,
        "pr": pr_number,
        "findings": len(report.all_findings),
        "health_score": report.health_score,
        "comment_posted": posted,
    }
