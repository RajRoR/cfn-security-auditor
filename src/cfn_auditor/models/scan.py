"""Scan model — one audit run against one CloudFormation template."""

from datetime import UTC, datetime
from enum import StrEnum

from sqlmodel import Field, Relationship, SQLModel

from cfn_auditor.models.finding import Finding

__all__ = ["Scan", "ScanStatus"]


class ScanStatus(StrEnum):
    """Lifecycle state of a scan."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


def _utcnow() -> datetime:
    """Return the current UTC time (factored out so tests can patch it)."""
    return datetime.now(UTC)


class Scan(SQLModel, table=True):
    """A single audit run: one template parsed, one rule pack executed."""

    __tablename__ = "scan"

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=_utcnow, index=True)
    template_name: str = Field(description="Original filename or label of the template.")
    status: ScanStatus = Field(default=ScanStatus.PENDING, index=True)
    error_message: str | None = Field(
        default=None,
        description="Populated when status is FAILED.",
    )
    finding_count: int = Field(default=0, ge=0)
    critical_count: int = Field(default=0, ge=0)
    high_count: int = Field(default=0, ge=0)
    medium_count: int = Field(default=0, ge=0)
    low_count: int = Field(default=0, ge=0)
    info_count: int = Field(default=0, ge=0)

    findings: list[Finding] = Relationship(
        back_populates="scan",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
