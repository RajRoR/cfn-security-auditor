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

---

## Turn 5 — 2026-05-31 · Elapsed 01:05

> PR #1 merged, branch protection on. New branch feat/parser. TDD - tests land in this PR.
>
> Build the parser layer: CloudFormation template (YAML or JSON) -> a normalized in-memory domain model. Scope tightly:
>
> 1. Entry point: parse_template(content: str | bytes, name: str) -> Template. Enforce the 5 MB size cap (from settings.max_template_bytes) on the raw bytes BEFORE parsing.
>
> 2. YAML: yaml.safe_load only, via a custom SafeLoader subclass that registers constructors for CloudFormation short-form intrinsics (!Ref, !GetAtt, !Sub, !Join, !Select, !Split, !GetAZs, !ImportValue, !Base64, !Cidr, !FindInMap, !If, !Condition, !And, !Or, !Not, !Equals) and converts each to its full-form dict ({"Ref": ...}, {"Fn::GetAtt": [...]}, etc.). Never yaml.load / full loader.
>
> 3. JSON: CFN can be JSON. Since JSON is valid YAML, the same CFN-aware safe loader can cover both - but prove it with a JSON fixture.
>
> 4. Normalized model (domain DTOs, NOT SQLModel - these are not persisted): Template(description, resources) and Resource(logical_id, type, properties: dict, raw). Define them in the parser layer so rules can import them. We do NOT evaluate Parameters/Conditions/Mappings or resolve intrinsics - we normalize short tags to full-form data and leave them as-is. This is a static structural parse.
>
> 5. Named domain errors (per our error-handling standard, clear messages, no sensitive data): TemplateParseError (base), MalformedTemplateError, TemplateTooLargeError, NotACloudFormationTemplateError (top-level not a mapping, or no Resources mapping).
>
> 6. Tests first, in the same PR, covering: YAML with short tags normalizes to full form; equivalent JSON parses to the same model; resources extracted with logical_id/type/properties; malformed YAML and malformed JSON raise MalformedTemplateError; oversize raises TemplateTooLargeError; missing/empty Resources raises NotACloudFormationTemplateError; empty input. Keep coverage >= 85.
>
> Stop after the parser + its tests. Show me the Template/Resource model, the short-tag loader, and the pytest output. Do NOT write rules, scoring, or API yet.

---

## Turn 6 — 2026-05-31 · Elapsed 01:25

> Strong parser turn - approved, with changes folded into this same PR before you open it.
>
> CLAUDE.md (security section), two lines, both documenting this PR's parser:
> 1. The loader is correct, but the contract still says "Never yaml.load," which this PR contradicts. Refine that line to the real intent: "Use yaml.safe_load, or yaml.load ONLY with an explicit SafeLoader subclass (our CfnSafeLoader). Never the default/Full/Unsafe loader." Bless CfnSafeLoader by name.
> 2. Add a known-limitation note: "YAML alias-expansion (billion-laughs) amplification is NOT mitigated beyond the input size cap; safe_load does not bound expanded node count. Current mitigation: the max_template_bytes cap. Hardening (node/depth limit) tracked for the security chore." Don't implement the node limit now - just document it.
>
> Code (this is the one behavioral change):
> 3. Unknown-tag resilience. Right now an unmapped CFN short tag raises ConstructorError -> MalformedTemplateError, so one exotic intrinsic makes us refuse to scan the whole template - wrong failure mode for an auditor. Register a fallback on CfnSafeLoader (add_multi_constructor for the "!" prefix) that preserves any unrecognized tag as opaque data keyed by its tag name instead of raising, and log a warning naming the tag. Specific constructors (!Ref etc.) must still take precedence. Add a test: a template with an unknown !Tag still parses, its other resources are intact, and a warning is emitted. We fail open on the one node, never closed on the file.
>
> Confirmed answers: (b) yes, Properties -> {} when absent is correct, keep it. (c) tag coverage is sufficient - the fallback is the fix, don't add more tags.
>
> Then commit (feat: parser layer - CFN YAML/JSON -> normalised Template/Resource), push feat/parser, open the PR to main, let CI run, report status. Do NOT merge; do NOT start rules/scoring/API.

---

## Turn 7 — 2026-05-31 · Elapsed 01:40

> PR #2 merged. Next branch: feat/rules. Build the rule framework, then (after my review) a first batch of 10 guardrails. Static analysis only - rules read the parsed Template/Resource model, no AWS, no intrinsic evaluation.
>
> Architectural contract (lock this first):
> 1. RuleFinding: a frozen dataclass DTO (rule_id, severity, resource_logical_id, message, remediation). Rules return list[RuleFinding]. Rules MUST NOT import the db/models layer - the engine (later turn) maps RuleFinding -> the persisted Finding SQLModel. Keep the parser/rules -> db direction intact.
> 2. Severity: an enum (CRITICAL, HIGH, MEDIUM, LOW). No score weighting yet - that's the scoring turn. Just the enum.
> 3. Registry: an explicit @register decorator appending to a module-level list, plus an all_rules() accessor. No auto-discovery magic beyond one explicit import of the rules package. The registry must raise on a duplicate rule id.
> 4. Rule base class: stable id, title, severity, resource_types (the CFN types it applies to), and evaluate(resource, template) -> list[RuleFinding].
>
> Unresolved-intrinsic handling (this is part of the contract, and it shapes S3-001):
> - Because we do not evaluate intrinsics, property values may be intrinsic dicts (e.g. {"Ref": ...}, {"Fn::If": [...]}) instead of literals.
> - Add a shared helper, literal_or_none(value), that returns the value only if it is a literal (str/bool/int/list/dict-that-isn't-an-intrinsic) and None if it is an unresolved intrinsic.
> - Rule semantics: (a) absence checks fire on a missing property regardless; (b) insecure-literal checks fire ONLY on the literal insecure value; (c) when the property is PRESENT but its value is an unresolved intrinsic, emit NO finding - we cannot assert it's insecure. Document this as a known limitation. Never crash on an intrinsic where a literal was expected.
>
> STOP after the framework + ONE reference rule (S3-001: AWS::S3::Bucket missing BucketEncryption) wired end-to-end, with fixture tests covering pass (encryption present), fail (absent), and the intrinsic case (BucketEncryption is an !If -> no finding). Surface the Rule base class, Severity enum, registry, RuleFinding DTO, literal_or_none, and S3-001 for my review. Do NOT write the other 9 rules, the engine, scoring, or API yet. Do NOT open a PR yet.
>
> Forward notes so the batch turn doesn't guess (do NOT implement now, just keep in mind):
> - IAM rules must only fire on Effect: Allow statements; PolicyDocument.Statement may be a single dict or a list; Action/Resource may be a string or a list. MVP flags the literal full wildcard "*", not service-scoped "s3:*".
> - SG rules scope to AWS::EC2::SecurityGroup inline SecurityGroupIngress; standalone AWS::EC2::SecurityGroupIngress resources are a known limitation for MVP.
>
> Each rule self-tests with tiny inline pass/fail templates. Do NOT build the clean/medium/critical oracle templates - those are for the engine turn.

---

## Turn 8 — 2026-05-31 · Elapsed 02:00

> Framework approved - it's the contract I wanted. One fix before you commit, because S3-001 is the reference the other rules copy:
>
> 1. S3-001 evaluate has a dead branch: both the "literal_or_none(...) is None" arm and the fallthrough return []. The literal_or_none call is dead code here - S3-001 is a pure absence check, so a present BucketEncryption is a pass regardless of literal-vs-intrinsic. Strip evaluate to: if "BucketEncryption" in resource.properties -> return []; else -> return [the finding]. Keep the !If and !Ref tests (they correctly document we don't false-positive when encryption is defined via an intrinsic). Also fix the summary wording: literal_or_none is exercised by test_framework, not by S3-001 itself.
>
> Then commit (feat: rules framework + S3-001 missing BucketEncryption), push feat/rules, open the PR to main, let CI run, report status. Do NOT merge; do NOT start the 9-rule batch, the engine, scoring, or API yet.
>
> Confirmed for the NEXT turn (don't build yet) - the locked 9-rule batch, all deterministic, no heuristics:
> - CFN_S3_002 PublicAccessBlockConfiguration missing or any flag literally false (CRITICAL)
> - CFN_S3_003 bucket ACL PublicRead/PublicReadWrite (CRITICAL)
> - CFN_SG_001 ingress from 0.0.0.0/0 or ::/0 - HIGH, escalates to CRITICAL when the port range covers 22 or 3389 (one rule, conditional severity)
> - CFN_IAM_001 Allow statement with Action "*" (HIGH)
> - CFN_IAM_002 Allow statement with Resource "*" (MEDIUM)
> - CFN_RDS_001 StorageEncrypted false/absent (HIGH)
> - CFN_RDS_002 PubliclyAccessible true (CRITICAL)
> - CFN_EC2_001 EBS volume/block device unencrypted (MEDIUM)
> - CFN_CT_001 CloudTrail trail without KMSKeyId (MEDIUM)
> The Lambda plaintext-secret heuristic is cut from MVP (fuzzy, false-positive-prone) - defer to a labelled heuristic set post-MVP. Every value-based rule (S3_002 flags, SG port, RDS_001/002, EC2_001) must carry the full pass / insecure-literal-fires / unresolved-intrinsic-no-finding test triad.

---

## Turn 9 — 2026-05-31 · Elapsed 02:15

> PR #3 approved and merged. Next branch: feat/rules-batch. Build the locked 9 guardrails against the parsed model. Static only, no AWS, no intrinsic evaluation. One PR for all nine.
>
> Layout: one file per service under rules/checks/ (sg.py, iam.py, rds.py, ec2.py, cloudtrail.py), mirroring s3.py. Update rules/checks/__init__.py to import every service module so each @register side-effect fires - an unimported rule silently never runs. Add a test asserting all 10 expected rule ids are present in all_rules().
>
> The 9 rules:
> - CFN_S3_002 AWS::S3::Bucket: PublicAccessBlockConfiguration missing, or any of BlockPublicAcls/IgnorePublicAcls/BlockPublicPolicy/RestrictPublicBuckets literally false (CRITICAL)
> - CFN_S3_003 AWS::S3::Bucket: AccessControl is PublicRead or PublicReadWrite (CRITICAL)
> - CFN_SG_001 AWS::EC2::SecurityGroup: an inline SecurityGroupIngress entry with CidrIp 0.0.0.0/0 or CidrIpv6 ::/0. HIGH, escalates to CRITICAL when the port range (FromPort..ToPort) covers 22 or 3389. Standalone AWS::EC2::SecurityGroupIngress resources are a documented MVP limitation.
> - CFN_IAM_001 policy with an Allow statement whose Action includes the literal "*" (HIGH)
> - CFN_IAM_002 policy with an Allow statement whose Resource includes the literal "*" (MEDIUM)
> - CFN_RDS_001 AWS::RDS::DBInstance: StorageEncrypted literally false or absent (HIGH)
> - CFN_RDS_002 AWS::RDS::DBInstance: PubliclyAccessible literally true (CRITICAL)
> - CFN_EC2_001 AWS::EC2::Volume: Encrypted literally false or absent (MEDIUM)
> - CFN_CT_001 AWS::CloudTrail::Trail: KMSKeyId absent (MEDIUM)
>
> IAM correctness (apply to whichever IAM resource types carry a PolicyDocument): fire only on Effect: Allow; Statement may be a single dict or a list - normalise; Action/Resource may be a string or a list - normalise; match the literal full wildcard "*", not service-scoped like "s3:*".
>
> Intrinsic contract via literal_or_none: for every value-based check, an unresolved-intrinsic value means we cannot assert insecurity - emit no finding. Each value-based rule (S3_002 flags, SG port/cidr, RDS_001/002, EC2_001) carries the full triad test: secure-literal -> no finding, insecure-literal -> fires, unresolved-intrinsic -> no finding. Pure absence/presence rules (CT_001, IAM presence) don't need the intrinsic arm.
>
> Tiny inline pass/fail fixtures per rule. Do NOT build the clean/medium/critical oracle templates - those are the engine turn. Do NOT build the engine, scoring, or API. Keep coverage >= 85. Then commit (feat: rules batch - 9 guardrails across S3/SG/IAM/RDS/EC2/CloudTrail), push feat/rules-batch, open the PR, report CI. Do NOT merge.

---

## Turn 10 — 2026-05-31 · Elapsed 02:45

> PR #4 is merged — thanks. Quick closure on your two questions before the next turn:
> (a) Merged by me, per the human-only-merge rule. main now contains the rules batch.
> (b) feat/engine scope is confirmed and scoring stays its own later turn (not pulled forward) — but that's the turn AFTER this one. I'll send the engine prompt next. Do NOT start the engine in this turn.
>
> This turn is a governance/contract turn. Branch: docs/contract-hardening (branch off latest main). CLAUDE.md only (plus the prompts.md entry).
>
> Under "Commits & PRs":
> - **Claude never merges.** Claude may create branches, push commits, and open PRs, then stop after reporting CI status. The human performs every merge. "Open the PR" never implies merging it. Claude must wait for an explicit merge confirmation before starting the next turn.
> - **No dependency or version changes without explicit human approval.** Adding/removing a dependency or changing a pinned version requires the human to approve it first in a prompt. (Tooling bumps forced by the runtime, like a linter that must parse py314, still require explicit sign-off.)
>
> Under "Security Standards":
> - **Error messages never echo template content.** Parser and rule errors name the template label and the logical id, never the offending source text, so untrusted template content cannot leak through logs or API responses.
>
> New short section "Resilience" (after Architecture):
> - **Fail open, never closed.** The auditor degrades gracefully and warns; it never refuses to scan because of one unparseable or unknown node. A single rule that raises must not abort the scan: the engine isolates per-rule failures, logs them, records them, and continues evaluating the remaining rules and resources.
>
> New short section "Rules Authoring" (after Resilience):
> - **Rule IDs are CFN_<SERVICE>_<NNN>** (e.g. CFN_S3_001), stable and never reused once published.
> - **Intrinsic contract.** Rules read literal values via literal_or_none. Absence checks fire on a missing property; insecure-literal checks fire only on the literal insecure value; a property present but holding an unresolved intrinsic emits no finding and never crashes. We never assert (in)security we cannot statically prove.
> - **Rules return RuleFinding and never import models/db.** The engine maps RuleFinding to the persisted Finding; the dependency direction is rules -> parser only.
>
> Append the prompts.md turn entry in the fixed-header format. Commit (docs: harden standing contract - merge gate, fail-open, error hygiene, dependency approval, rules-authoring), push, open the PR, report CI. Do NOT merge.

---

## Turn 11 — 2026-05-31 · Elapsed 02:55

> PR #5 merged — thanks; main now carries the hardened contract. Engine turn.
>
> Branch: feat/engine. Goal: an orchestrator that turns raw template content into a persisted Scan with its Findings, honoring the fail-open and single-write-path contracts now in CLAUDE.md.
>
> Scope (one PR):
>
> 1. Engine entry point (e.g. engine/scanner.py): run_scan(content: str, name: str, session: Session) -> Scan. Inject the SQLModel Session — do not create a global. Flow:
>    - Parse via parser.parse_template(content, name). A genuine parse failure (malformed YAML, oversize, root not a mapping) raises the parser's typed error — let it propagate; do NOT swallow it into a fake empty scan. Fail-open governs bad *nodes* (the parser already degrades per-node), not an entirely unparseable file.
>    - For each resource, for each registered rule whose resource_types matches resource.type, call rule.evaluate(resource, template) inside its own try/except. On exception: log at error level with rule id + resource logical id + exception type ONLY — never template content (error-hygiene contract) — and continue. One raising rule must not abort the scan or skip other rules/resources. Durable persistence of rule-execution errors is out of scope (would need a new column) — log only, and note it deferred.
>    - Map each RuleFinding to a persisted Finding. RuleFinding carries rule_id, severity, resource_logical_id, message, remediation; supply resource_type from the Resource being evaluated (RuleFinding does not carry it). Respect the existing Finding schema — do not invent fields. If a required Finding column has no source from RuleFinding/rule/resource, stop and ask rather than guessing.
>    - Finalization (single-write-path): after all findings are collected, compute the denormalized counters on Scan (finding_count + per-severity counts) exactly once and write them. Never increment incrementally. Do it in one transaction with the finding inserts.
>    - Do NOT add columns to Scan/Finding this turn. If finalization seems to need a new field (e.g. a status), stop and ask — do not migrate silently.
>
> 2. Oracle integration fixtures — three realistic templates under tests/fixtures/: clean (no findings), medium (a couple of MEDIUM/HIGH issues), critical (at least one CRITICAL). These are the end-to-end fixtures deferred from the rules batch. Integration test: run_scan on each, assert the finding set and the finalized counters match expectations. Use an in-memory SQLite session with StaticPool + check_same_thread=False per CLAUDE.md.
>
> 3. Resilience unit test (the important one): register a deliberately-throwing rule via a fixture that adds it to the registry and removes it afterward (no registry leakage — deterministic tests). Run a scan; assert the scan still finalizes, the throwing rule yields no finding, every other rule's findings are present, and the failure was logged.
>
> Out of scope: scoring/grading (next turn — Scan keeps raw counts only), the FastAPI layer, the Streamlit dashboard.
>
> Keep coverage >= 85. Standard PR ritual per CLAUDE.md. Commit (feat: engine - orchestrate parse -> rules -> persisted scan/findings with per-rule isolation). Do NOT merge.

---

## Turn 12 — 2026-05-31 · Elapsed 03:30

> PR #6 merged — thanks. Scoring turn.
>
> Branch: feat/scoring. Goal: a pure, deterministic scoring function that turns a scan's severity counts into a numeric score, a letter grade, and a pass/fail gate decision. No persistence, no schema change this turn.
>
> Scope (one PR):
>
> 1. New module src/cfn_auditor/scoring.py — a leaf module that imports ONLY cfn_auditor.models.Severity (no engine, no db, no I/O). Expose via __all__.
>    - A frozen dataclass ScoreResult(score: int, grade: str, passed: bool).
>    - score(counts) -> ScoreResult where counts is the denormalized severity mapping already on a Scan (critical/high/medium/low/info). Accept either a Scan or a plain mapping — your call, but keep the signature typed and documented; do NOT import Scan if a mapping suffices (prefer the looser coupling).
>    - Locked, module-constant penalty weights (these are the contract — document them in the docstring): CRITICAL=40, HIGH=20, MEDIUM=10, LOW=3, INFO=0.
>    - score = max(0, 100 - sum(weight * count)). Integer.
>    - Letter grade bands: A >=90, B >=80, C >=70, D >=60, else F.
>    - Gate semantic (document it explicitly): passed = (critical_count == 0). A pre-deploy gate fails on any CRITICAL regardless of score; grade is informational. Do not also gate on score this turn — one gate rule, clearly stated.
>
> 2. Pure unit tests (tests/test_scoring.py): 
>    - The three oracle expectations from the engine turn: clean -> 100/A/passed; medium (HIGH=1, MEDIUM=3) -> score 50, grade F, passed True (no criticals); critical (CRITICAL=4, HIGH=3, MEDIUM=1) -> score 0, grade F, passed False. Verify these arithmetic results exactly.
>    - Grade-band boundary tests (89/90, 79/80, 69/70, 59/60) driven by synthetic count mappings.
>    - The gate: a single CRITICAL flips passed to False even when score is otherwise high; zero criticals with many lower-severity findings stays passed True.
>
> Do NOT wire scoring into the engine, the Scan model, or any persistence this turn. Do NOT touch the API. If you find a reason scoring MUST be persisted to work, stop and ask rather than adding a column.
>
> Open question to answer in the PR body (do not act on it): should grade/score be persisted on Scan for SQL-level filtering, or computed on read at the API boundary? Recommend, don't implement.
>
> Keep coverage >= 85. Standard PR ritual per CLAUDE.md. Commit (feat: scoring - deterministic score/grade/gate from severity counts). Do NOT merge.
