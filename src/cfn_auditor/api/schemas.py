"""Pydantic response schemas for the HTTP API.

Schemas live here (not on SQLModel rows or registered Rule classes directly)
so the wire format is decoupled from internal types. Routes return these.

Scoring is computed on read at the boundary (per PR #7's recommendation);
``score``, ``grade``, and ``passed`` are not persisted on the ``Scan`` table.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from cfn_auditor.models import Scan, ScanStatus, Severity
from cfn_auditor.rules import Severity as RuleSeverity
from cfn_auditor.scoring import score as compute_score

__all__ = [
    "FindingResponse",
    "HealthResponse",
    "RuleResponse",
    "ScanCreateRequest",
    "ScanDetailResponse",
    "ScanSummaryResponse",
    "ScoreResponse",
]


class HealthResponse(BaseModel):
    """Liveness response."""

    status: str = Field(description="Constant 'ok' for healthy.")


class RuleResponse(BaseModel):
    """Public metadata for a registered guardrail rule.

    Mirrors the ``Rule`` class's class vars: ``id``, ``title``, ``severity``,
    and ``resource_types``. ``Rule`` does not currently carry a remediation
    string (remediation lives on ``RuleFinding``), so it is not exposed here.
    """

    id: str
    title: str
    severity: RuleSeverity
    resource_types: list[str] = Field(
        description="CloudFormation resource types the rule applies to, sorted."
    )


class ScanCreateRequest(BaseModel):
    """JSON body for POST /scans.

    Either ``template`` (raw YAML/JSON content) is required. ``name`` is an
    optional caller-supplied label used in diagnostics; defaults to
    ``template`` when absent.
    """

    template: str = Field(min_length=1, description="Raw CloudFormation template content.")
    name: str = Field(default="template", description="Label for the template.")


class ScoreResponse(BaseModel):
    """Computed score / grade / pre-deploy gate."""

    score: int = Field(ge=0, le=100)
    grade: str = Field(description="Letter grade A/B/C/D/F.")
    passed: bool = Field(description="Pre-deploy gate result; True when no CRITICAL findings.")


class FindingResponse(BaseModel):
    """One persisted finding on a scan."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    rule_id: str
    severity: Severity
    resource_logical_id: str
    resource_type: str
    message: str


class ScanSummaryResponse(BaseModel):
    """Scan list-row: counters and computed scoring; no findings."""

    id: int
    created_at: datetime
    template_name: str
    status: ScanStatus
    finding_count: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    info_count: int
    score: ScoreResponse

    @classmethod
    def from_scan(cls, scan: Scan) -> ScanSummaryResponse:
        """Build a summary from a persisted ``Scan`` with compute-on-read scoring."""
        assert scan.id is not None
        return cls(
            id=scan.id,
            created_at=scan.created_at,
            template_name=scan.template_name,
            status=scan.status,
            finding_count=scan.finding_count,
            critical_count=scan.critical_count,
            high_count=scan.high_count,
            medium_count=scan.medium_count,
            low_count=scan.low_count,
            info_count=scan.info_count,
            score=_score_for(scan),
        )


class ScanDetailResponse(ScanSummaryResponse):
    """Full scan response: summary fields + findings."""

    findings: list[FindingResponse]

    @classmethod
    def from_scan(cls, scan: Scan) -> ScanDetailResponse:
        """Build a full detail response from a persisted ``Scan``."""
        assert scan.id is not None
        return cls(
            id=scan.id,
            created_at=scan.created_at,
            template_name=scan.template_name,
            status=scan.status,
            finding_count=scan.finding_count,
            critical_count=scan.critical_count,
            high_count=scan.high_count,
            medium_count=scan.medium_count,
            low_count=scan.low_count,
            info_count=scan.info_count,
            score=_score_for(scan),
            findings=[FindingResponse.model_validate(f) for f in scan.findings],
        )


def _score_for(scan: Scan) -> ScoreResponse:
    """Compute the score for ``scan`` from its denormalised counters."""
    counts: dict[Severity, int] = {
        Severity.CRITICAL: scan.critical_count,
        Severity.HIGH: scan.high_count,
        Severity.MEDIUM: scan.medium_count,
        Severity.LOW: scan.low_count,
        Severity.INFO: scan.info_count,
    }
    result = compute_score(counts)
    return ScoreResponse(score=result.score, grade=result.grade, passed=result.passed)
