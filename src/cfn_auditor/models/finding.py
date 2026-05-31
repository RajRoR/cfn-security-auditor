"""Finding model — one rule violation against one resource in one scan."""

from enum import StrEnum
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from cfn_auditor.models.scan import Scan

__all__ = ["Finding", "Severity"]


class Severity(StrEnum):
    """Severity of a guardrail violation."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class Finding(SQLModel, table=True):
    """A single violation surfaced by a rule against a CloudFormation resource."""

    __tablename__ = "finding"

    id: int | None = Field(default=None, primary_key=True)
    scan_id: int = Field(foreign_key="scan.id", index=True)
    rule_id: str = Field(index=True, description="Stable rule identifier, e.g. CFN_S3_001.")
    severity: Severity = Field(index=True)
    resource_logical_id: str = Field(
        description="CloudFormation logical ID (the key under Resources)."
    )
    resource_type: str = Field(description="CloudFormation type, e.g. AWS::S3::Bucket.")
    message: str = Field(description="Human-readable explanation of the violation.")

    scan: "Scan" = Relationship(back_populates="findings")  # noqa: UP037
