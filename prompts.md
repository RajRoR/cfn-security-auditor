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
