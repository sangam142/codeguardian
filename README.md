# CodeGuardian

Multi-agent code review for pull requests. A supervisor looks at what changed
and fans the work out to four specialist agents — security, quality, test
gaps, documentation. Each agent pairs deterministic tools (Bandit, a secret
scanner, AST-based checkers) with an optional LLM pass that explains and ranks
what the tools found. The LLM never invents findings: if a tool didn't flag
it, it isn't in the report.

A review comes back as one severity-ranked Markdown report with a code-health
score. Every run is recorded to SQLite and charted on a small dashboard.

The whole core pipeline runs with **no API keys**. Keys only unlock extras:
plain-English explanations and posting real PR comments.

## Quickstart

```bash
pip install -r requirements.txt
python -m app.harness sample_vulnerable_code
```

That prints a ranked report of real issues found in the bundled sample code —
command injection, hardcoded credentials, `eval` on file contents, missing
tests, missing docstrings. Each run is also recorded to `data/history.db` for
the dashboard (skip with `--no-history`).

## Server and dashboard

```bash
cp .env.example .env      # optional; everything works with blank values
uvicorn app.main:app --reload
```

Open <http://localhost:8000/dashboard> to see the code-health score over
time, finding counts by severity and by agent, and the recent-review table.
The "Run Demo Scan" button reviews `sample_vulnerable_code` live, so there's
something to look at on a fresh install.

To review actual pull requests, expose the server (ngrok, [smee.io]) and
point a repo webhook (`pull_request` events) at `/webhook`. The PR head is
shallow-cloned into a temp dir and reviewed for real. Without a
`GITHUB_TOKEN` it runs dry: the comment it would have posted goes to the
server log instead of GitHub.

## Optional: LLM triage

Put an `LLM_API_KEY` in `.env` ([Groq][console.groq.com] has a free tier) and
findings gain short risk explanations and fix hints. Any OpenAI-compatible
endpoint works — Groq, Ollama, OpenAI — via `LLM_BASE_URL` / `LLM_MODEL`.

The quality agent's explanations are grounded with retrieval: the codebase
under review plus [docs/coding_standards.md](docs/coding_standards.md) get
chunked and indexed (ChromaDB when installed, a keyword scorer otherwise),
and the most relevant chunks go into the triage prompt. The point is advice
that cites the house rules instead of generic lint wisdom.

## Auto-fix

```bash
python -m app.autofix sample_vulnerable_code            # propose only
python -m app.autofix sample_vulnerable_code --apply    # apply after y/N
```

The LLM drafts minimal patches for a review's findings. Every patch is
validated before it's shown — the original snippet has to match the target
file exactly once — and proposals land in `.codeguardian/fixes.md` for
reading. Nothing touches the working tree without `--apply` plus an explicit
confirmation, and CodeGuardian never commits, pushes, or opens PRs on its
own.

## How it works

```
GitHub PR ──► FastAPI /webhook ──► PR-head checkout ──► run_review(path)
                                                             │
                                                        LangGraph
                                                             │
              ┌───── supervisor ── file census, pick agents
              │
              ├───── specialists ── security   (Bandit + secret scanner)
              │                     quality    (AST complexity/style + RAG)
              │                     test gaps  (untested public API)
              │                     docs       (docstrings + README)
              │                       └─ each: tools → findings → LLM triage
              │
              └───── aggregate ─── ReviewReport ──► ranked Markdown comment
                                        │
                                   SQLite history ──► /dashboard charts
```

Routing is a cheap file census, not another LLM call: a docs-only PR runs
just the documentation agent, JS/TS still gets security, Python gets all
four.

## Layout

| Path | What it is |
|------|------------|
| `app/graph.py` | LangGraph orchestration (three nodes) |
| `app/agents/supervisor.py` | classification + agent routing |
| `app/agents/{security,quality,test_gap,documentation}.py` | the specialists |
| `app/tools/` | deterministic scanners (Bandit, secrets, complexity, test gaps, docs) |
| `app/rag.py` | ChromaDB / keyword retrieval for the quality agent |
| `app/llm.py` | optional LLM enrichment — explains, never invents |
| `app/review.py` | single entry point + report formatting |
| `app/history.py` | SQLite review history behind the dashboard |
| `app/main.py` | FastAPI webhook, dashboard, JSON API |
| `app/static/dashboard.html` | the dashboard (single file, React + SVG charts) |
| `app/autofix.py` | gated auto-fix CLI |
| `app/harness.py` | local CLI runner |

## HTTP API

| Endpoint | What it does |
|----------|--------------|
| `POST /webhook` | GitHub PR events (HMAC-verified) → review → PR comment |
| `GET /dashboard` | the dashboard UI |
| `GET /api/history?limit=100` | recent reviews, oldest first |
| `GET /api/summary` | headline numbers |
| `POST /api/scan {"path": "..."}` | review a local path now (the demo button) |
| `GET /health` | liveness probe |

## Tests

```bash
python -m pytest
```

Covers the scoring model, every deterministic tool, supervisor routing, RAG
retrieval, history persistence, webhook signature/event handling, and the
auto-fix safety rails. The suite runs fully offline — no LLM, no network,
temp databases only.

## Future work

- Semgrep / Gitleaks runners next to Bandit
- coverage-based test-gap detection instead of name matching
- run specialists in parallel
- auth on the dashboard API

MIT licensed.

[smee.io]: https://smee.io
[console.groq.com]: https://console.groq.com
