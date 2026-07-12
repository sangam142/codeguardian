"""
Thin GitHub client — just enough to post a PR comment.

If no GITHUB_TOKEN is configured we run in *dry-run* mode: the comment is
printed to the log and nothing is sent. That keeps the webhook fully runnable
with zero credentials, exactly like the harness.
"""
from __future__ import annotations

import httpx

from app.config import settings

_API = "https://api.github.com"


def post_pr_comment(repo: str, pr_number: int, body: str) -> bool:
    """Post `body` as an issue comment on `repo`#`pr_number`.

    Returns True if the comment was actually posted, False in dry-run mode or
    on failure. Never raises — a failed post must not break webhook handling.
    """
    if not settings.github_token:
        # Dry-run: show what we *would* post.
        print(f"[dry-run] would comment on {repo}#{pr_number}:\n{body}\n")
        return False

    url = f"{_API}/repos/{repo}/issues/{pr_number}/comments"
    headers = {
        "Authorization": f"Bearer {settings.github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    try:
        resp = httpx.post(url, headers=headers, json={"body": body}, timeout=30)
        resp.raise_for_status()
        return True
    except httpx.HTTPError as exc:
        print(f"[github] failed to post comment on {repo}#{pr_number}: {exc}")
        return False
