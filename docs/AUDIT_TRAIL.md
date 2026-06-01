# Audit Trail — Prompts → Pull Requests

This project was built turn-by-turn with Claude as the implementer and the
human as the only merger. Every prompt the human sent is captured verbatim
in [`../prompts.md`](../prompts.md). Every prompt produced exactly one
branch, which became exactly one PR, which the human reviewed and merged.

This file is the cross-reference: each turn → the PR it produced → the
merged commit on `main`. A reviewer can follow any change in the codebase
back to the prompt that asked for it.

## Process invariants

- **Claude never merges.** Branches and PRs are pushed by Claude; merges are performed by the human.
- **One prompt → one branch → one PR.** Branches use Conventional-Commit type prefixes (`chore/`, `feat/`, `fix/`, `docs/`).
- **Coverage floor enforced in CI.** Every merged PR cleared `--cov-fail-under=85` plus `ruff` / `black` / `mypy`.
- **Prompt audit log.** `prompts.md` headers carry turn number, date, and cumulative elapsed time; the chat-footer Elapsed value matches the file (single source of truth).

## Mapping

| Turn | Branch                          | PR    | Title (commit subject)                                                                                                                              |
|-----:|---------------------------------|-------|-----------------------------------------------------------------------------------------------------------------------------------------------------|
|  1   | _planning only — no PR_         | —     | Lead Architect mode, MVP scope, repo confirmation.                                                                                                  |
|  2   | `chore/bootstrap`               | #1    | chore: bootstrap project foundation                                                                                                                 |
|  3   | `chore/bootstrap` (in-PR fix)   | #1    | (folded into #1 — CLAUDE.md prompts.md header rule)                                                                                                 |
|  4   | `chore/bootstrap` (in-PR fix)   | #1    | (folded into #1 — stack pins, env var, data-model + testing rules)                                                                                  |
|  5   | `feat/parser`                   | #2    | feat: parser layer — CFN YAML/JSON → normalised Template/Resource                                                                                   |
|  6   | `feat/parser` (in-PR fix)       | #2    | (folded into #2 — fail-open unknown short tag, CfnSafeLoader bless, billion-laughs note)                                                            |
|  7   | `feat/rules`                    | #3    | feat: rules framework + S3-001 missing BucketEncryption                                                                                              |
|  8   | `feat/rules` (in-PR fix)        | #3    | (folded into #3 — S3-001 reduced to pure absence check)                                                                                             |
|  9   | `feat/rules-batch`              | #4    | feat: rules batch — 9 guardrails across S3/SG/IAM/RDS/EC2/CloudTrail                                                                                 |
| 10   | `docs/contract-hardening`       | #5    | docs: harden standing contract — merge gate, fail-open, error hygiene, dependency approval, rules-authoring                                         |
| 11   | `feat/engine`                   | #6    | feat: engine — orchestrate parse → rules → persisted scan/findings with per-rule isolation                                                           |
| 12   | `feat/scoring`                  | #7    | feat: scoring — deterministic score/grade/gate from severity counts                                                                                 |
| 13   | `feat/api-foundation`           | #8    | feat: api foundation — app factory, session dependency, optional api-key auth, /health + /rules                                                      |
| 14   | `feat/api-scans`                | #9    | feat: api scans — run/list/get scans with compute-on-read scoring + error mapping                                                                    |
| 15   | `feat/dashboard`                | #10   | feat: dashboard — streamlit client for scan/score/findings/trend over the API                                                                        |
| 16   | `feat/advisor-foundation`       | #11   | feat: advisor foundation — provider abstraction, static remediation provider, /scans/{id}/advice                                                      |
| 17   | `feat/advice-panel`             | #12   | feat: dashboard advice panel — per-finding remediation over /scans/{id}/advice                                                                       |
| 18   | `feat/advisor-llm`              | #13   | feat: advisor llm — anthropic remediation provider grounded by in-repo RAG, behind the provider abstraction, static fallback                          |
| 19   | `feat/observability`            | #14   | feat: observability — request-id middleware + structured JSON request logging                                                                         |
| 20   | `fix/correctness-loose-ends`    | #15   | fix: correctness loose ends — S3-002 remediation wording, drop non-standard WWW-Authenticate, echo X-Request-ID on 500                                |
| 21   | `docs/polish-and-packaging`     | #16   | docs: README, Docker/Compose, OpenAPI export, MIT license, Makefile, audit trail                                                              |
| 22   | `docs/deck`                     | #17   | docs: presentation deck                                                                                                                       |
| 24   | `feat/rate-limiting`            | #18   | feat: rate limiting - per-client window limiter, standards-compliant 429 + Retry-After                                                        |
| 24   | `feat/rate-limiting` (in-PR fix)| #18   | (folded into #18 - in-PR redaction fix on the limiter's log surface so the X-API-Key value never reaches stored logs)                         |
| 23   | `fix/dashboard-home-permission` | #19   | fix: create writable home for app user so the dashboard container boots                                                                       |
| 25   | `docs/sync-final-state`         | _this PR_ | docs: sync deck, audit trail, README to final state (#1-#19) + dashboard screenshot                                                       |

Turns 3, 4, 6, and 8 land as additional commits inside an already-open PR
because the human asked for them as in-PR review fixes before approving the
merge. They carry their own prompt entries in `prompts.md`; each is
attributable to a specific commit on the branch.

Turn 24 maps to PR #18 in two rows: the original prompt that produced the
limiter and the in-PR redaction fix folded in before merge. Turn 23 maps to
PR #19 even though its turn number sorts before Turn 24's because Turn 24
was renumbered during conflict resolution after PRs #17 and #19 had already
landed on `main`.

## How to use this file

- Pick any line in the codebase and run `git blame` to find the merge
  commit; cross-reference the merge commit message to the PR number; look
  up the PR in this table for the turn that produced it; read the prompt
  in `prompts.md` for the full directive.
- Conversely, pick a turn from `prompts.md`; find it here; jump to the PR
  on GitHub for the diff and CI receipts.
