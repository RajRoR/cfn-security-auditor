---
marp: true
title: CFN Security Auditor
description: API-first static security guardrails for AWS CloudFormation, built turn-by-turn with Claude as implementer and the human as the only merger.
paginate: true
---

# CFN Security Auditor

API-first static security guardrails for AWS CloudFormation – offline, pre-deploy, reproducible.

Built turn-by-turn with Claude as implementer and the human as the only merger.

`github.com/RajRoR/cfn-security-auditor`

---

## Problem

- Misconfigured CFN reaches AWS – encrypted? public? wide-open SG? – every day.
- Live scanning needs credentials, costs latency, fails on quotas, can't run in PR CI.
- A pre-deploy gate has to be **offline, deterministic, and fast** or it doesn't get used.
- Static analysis on the template is the right shape: same input → same findings, every run.
- Free tier: zero AWS calls, no boto3, no IAM provisioning per environment.

---

## Architecture

```
┌──────────────┐    HTTP (X-API-Key)    ┌─────────────┐
│  Dashboard   │ ─────────────────────▶ │     API     │
│  (Streamlit) │                        │  (FastAPI)  │
└──────────────┘                        └──────┬──────┘
                                               │
              ┌────────────────────────────────┼─────────────────────────┐
              ▼                                ▼                         ▼
        ┌──────────┐                  ┌────────────────┐       ┌──────────────────┐
        │  engine  │ ───────────────▶ │ parser + rules │       │ advisor (RAG+LLM)│
        └────┬─────┘                  └────────────────┘       │  static fallback │
             ▼                                                 └──────────────────┘
        ┌─────────┐
        │ models  │  SQLModel: Scan, Finding (sqlite)
        └─────────┘

observability: request-id middleware + structured JSON logs on every route
```

- Strict layering: lower layers never import upper layers.
- Dashboard is a pure HTTP client – never imports the engine, rules, or db.

---

## The rule engine

- **Auto-registering rules.** `@register` decorator + side-effect import; the registry rejects duplicate ids; one explicit module owns the import set.
- **10 guardrails** across S3 / SG / IAM / RDS / EC2 / CloudTrail (CIS-style):
  S3 encryption, public-access block, public ACL · SG wide-open ingress (HIGH, CRITICAL on 22/3389) · IAM Action `*` · IAM Resource `*` · RDS unencrypted, RDS public · EBS unencrypted · CloudTrail without KMS.
- **Intrinsic-aware contract.** Property holds an unresolved `Ref`/`Fn::*` → no finding (we cannot prove insecurity statically). Fire only on **literal** insecure values or **provable absence**. Never crash on a literal-vs-intrinsic mismatch.
- **Resilient.** A rule that throws is logged and skipped; the rest of the scan still runs.

---

## Scoring + gate

- Pure leaf module – no engine, no db, no I/O.
- **Locked weights:** CRITICAL 40, HIGH 20, MEDIUM 10, LOW 3, INFO 0.
- `score = max(0, 100 – sum(weight × count))`. Bands: A ≥ 90 · B ≥ 80 · C ≥ 70 · D ≥ 60 · else F.
- **Gate:** `passed = (critical_count == 0)`. One CRITICAL fails the pre-deploy regardless of score.
- **Compute-on-read** at the API boundary – never persisted on the `Scan` row, no schema drift when the contract is tuned.

---

## The GenAI angle – AI Remediation Advisor

- `GET /scans/{id}/advice` – per-finding remediation. One Protocol, two providers.
- **Static** (default): deterministic curated remediation keyed by `rule_id`. No network. `source: "static"`.
- **Anthropic** (opt-in via `CFN_AUDITOR_LLM_PROVIDER` + `CFN_AUDITOR_LLM_API_KEY`):
  - Lexical RAG over an in-repo corpus (`src/cfn_auditor/advisor/corpus/`, frontmatter-keyed).
  - Prompt grounds the model in retrieved control context + the finding, instructs "do not invent beyond it."
  - `source: "llm:<model>"` reflects actual provenance.
- **Fail-open at every layer:**
  - Construction failure → factory falls back to static.
  - Per-finding LLM error → that one item gets static remediation, `source: "static"`. The advise() call still returns.
- Dashboard caption renders `provider`/`source` verbatim – flips to `llm:...` with **zero UI change** when env vars are set. The Protocol earned its keep.

---

## Resilience + security posture

- **Fail-open, never closed.** One unparseable node, one throwing rule, one LLM hiccup, one limiter bookkeeping bug – never abort the scan or the advice call.
- **Error hygiene.** Response bodies and log lines **never** echo template content. Detail messages name the template label and the failure kind only. Regression tests pin this on the parse-failure path and the log surface.
- **Auth.** Optional `X-API-Key`; `secrets.compare_digest` for constant-time compare; standards-compliant 401 (`{"detail": ...}`, **no** non-standard `WWW-Authenticate: X-API-Key`).
- **Rate limiting** (PR #18). In-process per-client fixed-window limiter; opt-in via `CFN_AUDITOR_RATE_LIMIT_REQUESTS`; standards-compliant 429 + `Retry-After`; `/health` exempt; bookkeeping errors fail open. The same `X-Request-ID` rides on the 429.
- **Hardened container** (PR #19). The dashboard container runs non-root with a writable `$HOME=/home/app` so Streamlit's machine-id state file lands in a directory the unprivileged user actually owns.
- **Input controls.** YAML loaded only via a `yaml.SafeLoader` subclass (CFN short-tag aware, unknown-tag fallback); 5 MB hard cap on input bytes; billion-laughs documented as a known limitation behind the cap.
- **Observability.** `X-Request-ID` on every response (200, 401, 404, 429, 500) – generated when absent, propagated when supplied; structured JSON access log line with `request_id` / `method` / `path` / `status_code` / `duration_ms`.

---

## Engineering governance – human-in-the-loop

- **Claude never merges.** Pinned in `CLAUDE.md`. Claude opens PRs and stops; the human reviews and merges every one.
- **One prompt → one branch → one PR.** Conventional Commits (`feat:` / `fix:` / `docs:` / `chore:` / `ci:`).
- **CI merge gate** – same commands locally and in CI:
  `ruff check .` · `black --check .` · `mypy .` · `pytest --cov=src --cov-fail-under=85`.
- **No silent dependency changes.** New deps require an explicit human approval prompt; pinned + recorded in `CLAUDE.md`'s stack table.
- **Traceability.**
  – `prompts.md` – every prompt verbatim, with turn number, date, and cumulative elapsed.
  – `docs/AUDIT_TRAIL.md` – prompt → branch → merged PR mapping.
  – As-shipped: **19 merged PRs** (#1–#19), **252 tests**, **96.40% coverage** (last-measured on this PR); coverage floor 85%.

---

## Dashboard

![w:900](assets/dashboard-overview.png)

Visual risk score + gate badge and the per-finding remediation (advice) panel – the same data the API serves, severity-coloured.

---

## Live demo

```sh
# 1. Bring up the stack (API on :8000, dashboard on :8501).
make compose-up

# 2. Scan a deliberately-bad template.
curl -s -X POST http://localhost:8000/scans \
  -H 'X-Request-ID: demo-001' -H 'Content-Type: application/json' \
  -d @- <<'JSON' | jq .
{
  "name": "smoke.yaml",
  "template": "Resources:\n  PublicBucket:\n    Type: AWS::S3::Bucket\n    Properties:\n      AccessControl: PublicRead\n"
}
JSON

# 3. Read findings, score, gate.
curl -s http://localhost:8000/scans/1 | jq '.score, .findings[].rule_id'

# 4. Per-finding remediation. Set CFN_AUDITOR_LLM_* to flip source: "static" → "llm:..."
curl -s http://localhost:8000/scans/1/advice | jq '.provider, .items[].source'

# 5. Correlation: every response carries the same X-Request-ID; logs do too.
```

Visit `http://localhost:8501` for the dashboard – same data, severity-coloured, with score gauge, gate badge, advice panel, and score-over-time trend.

---

## What an FDE takes from this

- **Contract-first.** `CLAUDE.md` is the standing contract; every PR cites which rule it honours or extends.
- **Resilient by default.** Fail-open scanning, error hygiene on the response and log surfaces, single-write-path counters, explicit known-limitations.
- **AI as implementer under human control.** Claude built every line; the human reviewed every PR and merged every branch. The commit graph and `prompts.md` are the receipts.
- **Provider abstractions earn their keep.** `RemediationProvider` made the static→Anthropic swap a config change with zero UI/API code change.

Repo: `github.com/RajRoR/cfn-security-auditor`
Audit trail: `docs/AUDIT_TRAIL.md`
Standing contract: `CLAUDE.md`
Prompts (verbatim): `prompts.md`
