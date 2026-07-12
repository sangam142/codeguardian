"""FastAPI surface: health, signature checks, event filtering, dashboard API."""
from __future__ import annotations

import hashlib
import hmac
import json

from fastapi.testclient import TestClient

import app.main as main
from app.config import settings
from app.models import AgentReport, ReviewReport

client = TestClient(main.app)


def _signed(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_root_redirects_to_dashboard():
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert r.headers["location"] == "/dashboard"


def test_dashboard_serves_html():
    r = client.get("/dashboard")
    assert r.status_code == 200
    assert "CodeGuardian" in r.text


def test_webhook_rejects_bad_signature(monkeypatch):
    monkeypatch.setattr(settings, "github_webhook_secret", "topsecret")
    r = client.post("/webhook", content=b"{}",
                    headers={"X-GitHub-Event": "pull_request",
                             "X-Hub-Signature-256": "sha256=deadbeef"})
    assert r.status_code == 401


def test_webhook_ignores_other_events():
    r = client.post("/webhook", content=b"{}",
                    headers={"X-GitHub-Event": "push"})
    assert r.json() == {"skipped": "event 'push' ignored"}


def test_webhook_reviews_pr_and_records_history(monkeypatch):
    monkeypatch.setattr(settings, "github_webhook_secret", "topsecret")
    monkeypatch.setattr(main, "run_review",
                        lambda path: ReviewReport(codebase=path,
                                                  agent_reports=[AgentReport(agent="security")]))
    payload = {"action": "opened", "number": 42,
               "repository": {"full_name": "octo/demo"},
               "pull_request": {"head": {}}}
    body = json.dumps(payload).encode()
    r = client.post("/webhook", content=body,
                    headers={"X-GitHub-Event": "pull_request",
                             "X-Hub-Signature-256": _signed(body, "topsecret"),
                             "Content-Type": "application/json"})
    assert r.status_code == 200
    data = r.json()
    assert data["repo"] == "octo/demo" and data["pr"] == 42
    assert data["health_score"] == 100
    assert data["comment_posted"] is False  # dry-run without a token

    hist = client.get("/api/history").json()["reviews"]
    assert len(hist) == 1 and hist[0]["source"] == "webhook"
    assert client.get("/api/summary").json()["reviews"] == 1


def test_api_scan_records_review(tmp_path):
    (tmp_path / "x.py").write_text('"""doc."""\nX = 1\n')
    r = client.post("/api/scan", json={"path": str(tmp_path)})
    assert r.status_code == 200
    assert "health_score" in r.json()
    hist = client.get("/api/history").json()["reviews"]
    assert hist and hist[-1]["source"] == "api"
