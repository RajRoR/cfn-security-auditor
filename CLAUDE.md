# CLAUDE.md — Standing Contract

Read this file at the start of every turn. It is the source of truth for how this project is built. Deviations require an explicit instruction from the user.

## Project Overview

CFN Security Auditor is an API-first, Python-based enterprise security guardrail auditor that performs **static analysis on CloudFormation templates** (YAML/JSON) as a pre-deploy gate. It parses templates offline, runs a registry of guardrail rules against the parsed resources, persists scans and findings, and exposes them via a FastAPI HTTP API and a Streamlit dashboard. No live AWS calls; no boto3.

## Architecture (layered, strict dependency direction)

```
api          (FastAPI routes, request/response schemas)
  ↓
engine       (orchestrates a scan: parse → run rules → persist findings)
  ↓
rules        ← registry of auto-registered Rule classes
  ↓
parser       (YAML/JSON → normalized Template/Resource model)
  ↓
models/db    (SQLModel entities + session)
config       (pydantic-settings; leaf module, imported by anyone)
```

**Rule:** lower layers MUST NOT import from upper layers. `config` is a leaf and may be imported by any layer. The dashboard (Streamlit) consumes the API over HTTP — it does not import the engine.

## Data Model

The two persisted entities are `Scan` and `Finding` (one-to-many, cascading delete). Resource identity (`resource_logical_id`, `resource_type`) lives on `Finding`; there is no separate `Asset` table. Rules live in code as auto-registered classes and are exposed via `GET /rules` from the registry — they are not a DB table.

**Standing note:** the denormalized severity counts on `Scan` (`finding_count`, `critical_count`, `high_count`, `medium_count`, `low_count`, `info_count`) are a **single-write-path field**: derived from a scan's findings and written **once at scan finalization**, never hand-maintained. Anything that mutates findings must either go through that finalization path or be considered a bug.

## Stack (pinned)

| Layer        | Tool              | Pinned Version |
|--------------|-------------------|----------------|
| Language     | Python            | 3.14           |
| Package mgr  | uv                | latest         |
| Web API      | fastapi           | 0.115.x        |
| ASGI server  | uvicorn[standard] | 0.32.x         |
| ORM/models   | sqlmodel          | 0.0.22         |
| DB driver    | sqlite (stdlib)   | —              |
| Config       | pydantic-settings | 2.6.x          |
| YAML         | pyyaml            | 6.0.x          |
| Dashboard    | streamlit         | 1.40.x         |
| HTTP client  | httpx             | 0.28.x         |
| Tests        | pytest            | 8.3.x          |
| Coverage     | pytest-cov        | 6.0.x          |
| Lint         | ruff              | 0.14.x         |
| Format       | black             | 25.1.x         |
| Types        | mypy              | 1.13.x         |
| Pre-commit   | pre-commit        | 4.0.x          |

If a dep lacks a Python 3.14 wheel at install time, pin the nearest compatible version and document the exception in `pyproject.toml` with a comment.

## Coding Standards

- Full type hints on every function signature (no `Any` without justification).
- Docstrings on every public function/class (one-line summary minimum, args/returns when non-obvious).
- `ruff check .`, `black --check .`, and `mypy .` must be clean. Same commands locally and in CI.
- No bare `except`. Catch specific exceptions; chain with `raise ... from e` when re-raising.
- No `print`. Use the `logging` module with module-level loggers (`logger = logging.getLogger(__name__)`).
- No `eval`, no `exec`, no `os.system`, no `subprocess.shell=True`.
- Public modules expose their API via `__all__`.

## Linting = CI (exact commands)

```
ruff check .
black --check .
mypy .
pytest --cov=src --cov-report=term-missing --cov-fail-under=85
```

The CI workflow runs **exactly** these commands. Do not let local config diverge from CI.

## Testing

- TDD on domain code (parser, rules, engine). Tests land in the same PR as the code.
- `pytest` is the only test runner.
- Coverage floor is **85%**, enforced via `--cov-fail-under=85` in CI.
- Test layout mirrors source: `tests/<layer>/test_<module>.py`.
- Use `tmp_path` for file fixtures; never write outside the test sandbox.
- **In-memory SQLite test engines** must be created with `StaticPool` and `connect_args={"check_same_thread": False}` so a single shared in-memory database is visible across connections — required once `TestClient`/threaded API tests arrive. If `StaticPool` is not viable (e.g. parallel tests need isolation), use a temp-file SQLite DB per test instead.

## Commits & PRs

- **Conventional Commits**: `feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:`, `ci:`, `build:`.
- **One branch per turn**, named `<type>/<short-slug>` (e.g. `chore/bootstrap`, `feat/parser`).
- **Squash-merge** via PR. **No direct pushes to `main`.**
- PRs use the template at `.github/pull_request_template.md`.

## Security Standards (we eat our own dog food)

- YAML: `yaml.safe_load` only. Never `yaml.load`.
- Cap input file size (default 5 MB) before parse.
- Config: env vars only, via pydantic-settings. No secrets in code, no secrets in commits.
- Never shell out. Never `eval`/`exec`.
- API key auth: optional. If `CFN_AUDITOR_API_KEY` is unset, API is open (dev mode). If set, header `X-API-Key` required.
- Rule code is trusted (in-repo); never load rules from user-supplied paths or remote URLs.

## The Vibe-Coding Rule

Claude provides all code and fixes. The human reviews and merges; the human does **not** hand-edit code. If the human spots a problem, they describe it; Claude provides the fix in the next turn.

## Prompt Audit Log (`prompts.md`)

Every user prompt is logged in `prompts.md` using a **fixed header** followed by the prompt verbatim:

```
## Turn N — YYYY-MM-DD · Elapsed HH:MM

> <the verbatim prompt the user sent that turn>
```

- `N` is the turn number, monotonically increasing from 1.
- `Elapsed HH:MM` is the cumulative wall-clock time since T0 at the point that turn closed.
- The Elapsed value written to `prompts.md` **must match** the Elapsed value reported in that turn's chat footer. Single source of truth — they never drift.
- The prompt is preserved verbatim. No summarising, no editorialising.

## End-of-Turn Summary Format

Every turn ends with a summary block:

```
## Summary
- Changed: <one-line per significant change>
- Files touched: <count>
- Tests: <N passed / M failed>
- CI: <pending | green | red — link if available>
- Branch: <name>  PR: <url or "not yet opened">
- Elapsed: HH:MM (cumulative since T0)
- Open questions: <bullets, or "none">
```