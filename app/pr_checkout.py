"""
Check out a pull request's head commit into a throwaway temp dir so the review
runs against the *actual* PR code, not the server's own working directory.

Uses the plain `git` binary (already a dev dependency) instead of GitPython to
keep the dependency list small. Shallow-clones the head branch and pins the
exact head SHA, then cleans everything up when the caller is done.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from typing import Iterator

from app.config import settings


def _authed_url(clone_url: str) -> str:
    """Inject the token so private-repo clones work. Public repos are fine
    without it, but adding it is harmless and enables private repos."""
    if settings.github_token and clone_url.startswith("https://"):
        token = settings.github_token
        return clone_url.replace("https://", f"https://x-access-token:{token}@", 1)
    return clone_url


@contextmanager
def checkout_pr_head(payload: dict) -> Iterator[str]:
    """Yield a local path containing the PR head commit.

    On any failure (network, auth, git error) it yields the string ".", so the
    webhook degrades to reviewing the server's cwd rather than crashing. The
    temp dir is always removed on exit.
    """
    head = payload.get("pull_request", {}).get("head", {})
    clone_url = head.get("repo", {}).get("clone_url")
    ref = head.get("ref")
    sha = head.get("sha")

    if not clone_url or not sha:
        yield "."
        return

    tmp = tempfile.mkdtemp(prefix="cg_pr_")
    try:
        # Shallow-clone just the head branch, then pin the exact SHA.
        clone_cmd = ["git", "clone", "--quiet", "--depth", "1"]
        if ref:
            clone_cmd += ["--branch", ref]
        clone_cmd += [_authed_url(clone_url), tmp]

        subprocess.run(clone_cmd, check=True, capture_output=True, timeout=180)
        # Fetch + checkout the specific SHA in case the branch tip moved.
        subprocess.run(["git", "-C", tmp, "fetch", "--quiet", "--depth", "1",
                        "origin", sha], check=False, capture_output=True,
                       timeout=120)
        subprocess.run(["git", "-C", tmp, "checkout", "--quiet", sha],
                       check=False, capture_output=True, timeout=60)
        yield tmp
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired,
            FileNotFoundError):
        # git missing, clone failed, or timed out — degrade gracefully.
        yield "."
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
