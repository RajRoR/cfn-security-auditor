"""Scan orchestrator.

``run_scan`` is the single entry point that turns raw CloudFormation template
content into a persisted :class:`Scan` with its child :class:`Finding` rows.
The flow is intentionally narrow:

1. Parse via :func:`cfn_auditor.parser.parse_template`. A genuine parse
   failure (malformed YAML/JSON, oversize, root not a mapping) propagates the
   parser's typed error to the caller — we do not silently persist a fake
   empty scan. Fail-open governs bad **nodes** (the parser already degrades
   per-node), not an entirely unparseable file.
2. For every resource and every registered rule whose ``resource_types`` matches
   ``resource.type``, call ``rule.evaluate(resource, template)`` inside its
   own ``try`` / ``except``. A raising rule is logged and skipped; other rules
   and other resources continue to run.
3. Map each :class:`RuleFinding` to a persisted :class:`Finding` (the
   ``remediation`` field is dropped at this boundary — see the module docstring
   note below).
4. Finalisation: compute severity counters from the collected findings and
   write them onto the Scan **once**, in the same transaction as the
   findings.

Known limitation
----------------
The persisted :class:`Finding` schema does not carry a ``remediation`` column.
``RuleFinding.remediation`` is dropped at persistence; the remediation string
remains reachable in-process via the registered rule keyed by ``rule_id``. A
remediation column is deferred to a later schema turn.

Per-rule execution errors are logged with rule id, resource logical id, and
exception type — never template content (security/error-hygiene contract).
Durable persistence of those errors would require a new schema column and is
explicitly deferred.
"""

import logging

from sqlmodel import Session

from cfn_auditor.models import Finding, Scan, ScanStatus
from cfn_auditor.models import Severity as ModelSeverity
from cfn_auditor.parser import Resource, Template, parse_template
from cfn_auditor.rules import Rule, RuleFinding, all_rules

__all__ = ["run_scan"]

logger = logging.getLogger(__name__)


def run_scan(content: str, name: str, session: Session) -> Scan:
    """Run a full scan and persist a :class:`Scan` with its :class:`Finding` rows.

    Args:
        content: Raw CloudFormation template (YAML or JSON).
        name: Human-readable label for the template (typically a filename).
        session: SQLModel session in which to persist the scan and findings.

    Returns:
        The persisted :class:`Scan` (with ``id`` populated and counters set).

    Raises:
        TemplateParseError: When the template cannot be parsed at all.
            Subclasses are :class:`MalformedTemplateError`,
            :class:`TemplateTooLargeError`, and
            :class:`NotACloudFormationTemplateError`.
    """
    template = parse_template(content, name)
    rule_findings = _evaluate_all(template)
    return _persist(session, name, template, rule_findings)


def _evaluate_all(template: Template) -> list[tuple[RuleFinding, Resource]]:
    """Run every applicable rule against every resource, isolating failures.

    Returns a list of ``(RuleFinding, Resource)`` pairs so the persistence
    step can supply ``resource_type`` from the resource that produced each
    finding (``RuleFinding`` does not carry it).
    """
    pairs: list[tuple[RuleFinding, Resource]] = []
    for resource in template.resources:
        for rule in all_rules():
            if resource.type not in rule.resource_types:
                continue
            try:
                produced = rule.evaluate(resource, template)
            except Exception as exc:
                _log_rule_failure(rule, resource, exc)
                continue
            for finding in produced:
                pairs.append((finding, resource))
    return pairs


def _log_rule_failure(rule: Rule, resource: Resource, exc: BaseException) -> None:
    """Log a per-rule failure without echoing template content."""
    logger.error(
        "Rule %s raised %s while evaluating resource %s; skipping this rule "
        "for this resource and continuing the scan.",
        rule.id,
        type(exc).__name__,
        resource.logical_id,
    )


def _persist(
    session: Session,
    name: str,
    template: Template,
    rule_findings: list[tuple[RuleFinding, Resource]],
) -> Scan:
    """Materialise the Scan + Findings + finalised counters in one transaction."""
    scan = Scan(template_name=name, status=ScanStatus.RUNNING)
    for rf, resource in rule_findings:
        scan.findings.append(
            Finding(
                rule_id=rf.rule_id,
                severity=ModelSeverity(rf.severity.value),
                resource_logical_id=rf.resource_logical_id,
                resource_type=resource.type,
                message=rf.message,
            )
        )

    counts = _severity_counts(scan.findings)
    scan.finding_count = counts["finding_count"]
    scan.critical_count = counts["critical_count"]
    scan.high_count = counts["high_count"]
    scan.medium_count = counts["medium_count"]
    scan.low_count = counts["low_count"]
    scan.info_count = counts["info_count"]
    scan.status = ScanStatus.SUCCEEDED

    session.add(scan)
    session.commit()
    session.refresh(scan)

    logger.info(
        "Scan %s for template %s finalised with %d findings.",
        scan.id,
        name,
        scan.finding_count,
    )
    return scan


def _severity_counts(findings: list[Finding]) -> dict[str, int]:
    """Single-write-path severity counter computation."""
    counts: dict[str, int] = {
        "finding_count": len(findings),
        "critical_count": 0,
        "high_count": 0,
        "medium_count": 0,
        "low_count": 0,
        "info_count": 0,
    }
    bucket: dict[ModelSeverity, str] = {
        ModelSeverity.CRITICAL: "critical_count",
        ModelSeverity.HIGH: "high_count",
        ModelSeverity.MEDIUM: "medium_count",
        ModelSeverity.LOW: "low_count",
        ModelSeverity.INFO: "info_count",
    }
    for finding in findings:
        counts[bucket[finding.severity]] += 1
    return counts
