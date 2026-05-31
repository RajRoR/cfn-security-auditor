# Prompts Audit Log

> Chronological record of every user prompt sent to the Lead Architect agent. Updated each turn. Each entry uses a fixed header: turn number, date, and cumulative Elapsed Time, followed by the prompt verbatim.

---

## Turn 1 — 2026-05-31 · Elapsed 00:00

> Lead Architect mode: ON. We are building a Python-based, API-first Enterprise Security Guardrail Auditor using a free database and a dashboard.
>
> Rules:
> - No Manual Edits: You provide all logic and fixes. I will not edit any code.
> - Audit Log: You must maintain a file named prompts.md. After every turn, update that file (or provide the text block) with the prompt I just used.
> - Time-Check: Start a timer. Goal is an MVP in 4-6 hours (Max window: 16h). Report 'Elapsed Time' at the end of every response. Acknowledge and let's start.

---

## Turn 2 — 2026-05-31 · Elapsed 00:35

> Good Turn 1 – and yes, your CFN-static instinct is right. Lock these answers:
>
> 1. Cloud target: CFN static analysis only. We scan CloudFormation YAML/JSON templates offline, pre-deploy gate. No boto3, no live AWS, no mock AWS provider. Drop all three. We ship sample CFN templates as our test fixtures instead.
> 2. Auth: static API key from env is fine for MVP. Make it optional (no key set = open) so the dashboard and tests aren't blocked.
> 3. Repo layout: yes, scaffold greenfield in the current repo.
>
> Two corrections to your plan before you build:
>
> - Persistence is two tables only: Scan and Finding. Rules live in code as auto-registered classes, exposed via GET /rules from the registry – not a DB table. No Asset table; the resource identifier (logical ID + type) rides on the Finding. Don't over-model the MVP.
> - Keep uv + pyproject, FastAPI, SQLite, SQLModel, Streamlit, pytest. Add ruff + black + mypy as the lint/type stack, same commands locally and in CI so there's no drift.
>
> Now, before any feature code, lay the engineering foundation. Do all of this on a branch named chore/bootstrap and open a PR to main when done – nothing goes straight to main from here on.
>
> 1. CLAUDE.md at the repo root – our standing contract, you read it every turn:
>    - One-paragraph project overview + the layered architecture and dependency direction: api -> engine -> (parser, rules) -> models/db. config is a leaf; lower layers never import upper.
>    - Stack with pinned versions.
>    - Coding standards: full type hints, docstrings on public functions, ruff + black + mypy clean. No bare except, no print, use logging.
>    - Linting = CI: list the exact commands (ruff check ., black --check ., mypy .) and state they must match the workflow.
>    - Testing: TDD on domain code, tests land in the same PR, pytest, 85% coverage floor enforced in CI.
>    - Commits: Conventional Commits. Branch per turn. Squash-merge via PR. No direct pushes to main.
>    - PR template: Problem / Solution / How tested / Checklist.
>    - Security standards (we're a security tool, we eat our own dog food): yaml.safe_load only, cap input file size, env-only config, no secrets in code, no shelling out, no eval.
>    - The vibe-coding rule: you provide all fixes, the human never edits code.
>    - End-of-turn summary format (what changed, files touched, tests count + pass/fail, CI status, branch + PR, elapsed time, open questions).
>
> 2. GitHub Actions workflow on every PR and push: set up Python 3.14, install via uv, run ruff check, black --check, mypy, then pytest with coverage enforcing an 85% minimum. Single fast job.
>
> 3. Pre-commit config mirroring the CI checks.
>
> 4. pyproject.toml with all deps and tool config pinned. If any dep has no 3.14 wheel, pin the nearest compatible version and note it.
>
> 5. Scaffold the layered package structure (each layer a package with __init__.py), a config module using pydantic-settings, SQLModel definitions for Scan and Finding with fields + relationship, DB session setup, .gitignore, Makefile (test/run/lint), stub README, MIT LICENSE. Add one test that creates the tables and round-trips a Scan + Finding row so CI has something real to validate.
>
> Stop after the scaffold + DB models + that one test. Show me the directory tree and the Scan/Finding models, then pause. Do NOT write the parser, rules, scoring, or API yet – I review the foundation before we build on it.

---

## Turn 3 — 2026-05-31 · Elapsed 00:38

> One fix to prompts.md before you commit – the audit log has to be internally consistent, it's a graded artifact.
>
> Standardize every turn entry to the same format and backfill Turn 2:
>
>   `## Turn N — <date> · Elapsed <cumulative HH:MM>`
>   `<the verbatim prompt I used that turn>`
>
> Turn 2 is currently missing the Elapsed marker that Turn 1 has. Add it (use the cumulative elapsed at the point that turn closed).
>
> Then make it a standing rule in CLAUDE.md so it never drifts again: "Every prompts.md entry is logged with the turn number, date, and cumulative Elapsed Time in a fixed header, and the prompt verbatim. The Elapsed value reported in the chat footer and the one written to prompts.md must match." That keeps the chat footer and the file in sync from one source.
>
> Then proceed with the commit / push / PR as already approved.

---

## Turn 4 — 2026-05-31 · Elapsed 00:48

> Reviewed the PR off GitHub, not just your summary. CI is green – nice. Four fixes to CLAUDE.md before we merge, so the standing contract is self-consistent from commit one. All on chore/bootstrap, into PR #1.
>
> 1. The Stack table is stale: it still pins ruff 0.8.x and black 24.10.x, but pyproject pins ruff 0.14.x and black 25.1.x (the bump we approved). Update the table to match pyproject exactly, and double-check every other row matches the real pins too.
>
> 2. Security section says the API key env var is API_KEY. With env_prefix CFN_AUDITOR_, it's actually CFN_AUDITOR_API_KEY. Correct it.
>
> 3. Add the standing data-model note under the models section: "The denormalized severity counts on Scan (finding_count, critical_count, etc.) are a single-write-path field: derived from a scan's findings and written once at scan finalization, never hand-maintained."
>
> 4. Add to the Testing section: "The in-memory SQLite test engine must be created with StaticPool and check_same_thread=False so one shared in-memory database is visible across connections — required once TestClient/threaded API tests arrive. Otherwise use a temp-file SQLite DB per test."
>
> Commit as docs: tighten standing contract (...), push to chore/bootstrap, let CI re-run, and report the new CI status. Do NOT merge yet.
