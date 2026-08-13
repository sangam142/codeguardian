"""No-tunnel demo of the webhook security layer.

    python demo_webhook.py

Sends three requests straight into the ASGI app via FastAPI's TestClient:
  1. forged signature       -> 401 Bad signature
  2. valid signature        -> 200, accepted then filtered by action
  3. valid sig, wrong event -> 200, skipped

Uses action="closed" so the signature is verified but no review runs, which
keeps it instant. Works with no network, no GitHub, and no server running.
"""
import hashlib
import hmac
import json
import os
import sys

# Run from the project root: make `app` importable regardless of script location.
sys.path.insert(0, os.getcwd())

# Must be set BEFORE app.config is imported, so Settings.load() picks it up.
os.environ["GITHUB_WEBHOOK_SECRET"] = "demo-secret"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

SECRET = b"demo-secret"
client = TestClient(app)

payload = {
    "action": "closed",
    "number": 42,
    "repository": {"full_name": "sangam142/codeguardian-demo"},
    "pull_request": {
        "head": {
            "ref": "fix-deploy",
            "sha": "a1b2c3d4e5f6",
            "repo": {
                "clone_url": "https://github.com/sangam142/codeguardian-demo.git"
            },
        }
    },
}
body = json.dumps(payload).encode()
good = "sha256=" + hmac.new(SECRET, body, hashlib.sha256).hexdigest()
bad = "sha256=" + "0" * 64


def send(label: str, sig: str, event: str = "pull_request") -> None:
    resp = client.post(
        "/webhook",
        content=body,
        headers={
            "X-GitHub-Event": event,
            "X-Hub-Signature-256": sig,
            "Content-Type": "application/json",
        },
    )
    print(f"{label:<28} -> HTTP {resp.status_code}  {resp.json()}")


print("\n--- webhook security demo ---\n")
send("1. forged signature", bad)
send("2. valid signature", good)
send("3. valid sig, wrong event", good, event="issues")
print()
