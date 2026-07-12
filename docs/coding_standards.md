# CodeGuardian Coding Standards

The house rules the Quality Agent's RAG layer retrieves from when explaining
findings. Keep each rule short and actionable — chunks of this file are fed
verbatim to the LLM as grounding context.

## Functions

- Keep cyclomatic complexity at or below 10. If a function needs more
  branches, split the decision logic into named helpers.
- Keep functions under 60 lines. Long functions hide bugs and resist testing;
  extract cohesive blocks into helpers with descriptive names.
- Take at most 6 parameters. Group related parameters into a dataclass or a
  config object instead of growing the signature.
- Never use mutable default arguments (`def f(x=[])`). The default is created
  once and shared across calls. Use `None` and construct inside the body.
- Prefer early returns over deep nesting. Control flow nested more than four
  levels deep should be flattened or extracted.

## Error handling

- Never use a bare `except:`. It swallows `KeyboardInterrupt`, `SystemExit`,
  and typos alike. Catch the narrowest exception that the block can raise.
- Agents and tools in this codebase must never raise out of their entry
  point: catch internal errors and return a report with `error` set, so one
  failing component cannot sink a whole review.

## Security

- Secrets never live in source or templates. Use environment variables loaded
  from a git-ignored `.env`; keep `.env.example` values blank.
- Never build shell commands from user input; pass argument lists to
  `subprocess.run` and avoid `shell=True`.
- Validate webhook payloads with HMAC signatures before trusting any field.

## Testing

- Every public function should be exercised by at least one test that calls
  it directly. Test files live under `tests/` and are named `test_*.py`.
- Deterministic tools are tested against small fixture trees written to
  `tmp_path`, never against the live repository.

## Documentation

- Every module starts with a docstring saying what the module is *for*, not
  restating its name.
- Public classes and functions get docstrings describing behavior and edge
  cases (what happens on failure, what is never raised).

## Style

- `from __future__ import annotations` at the top of every module.
- Absolute imports rooted at `app.`.
- Forward-slash paths in anything rendered to users, so reports look the same
  on every OS.
