"""Pydantic response schemas for the HTTP API.

Schemas live here (not on SQLModel rows or registered Rule classes directly)
so the wire format is decoupled from internal types. Routes return these.
"""

from pydantic import BaseModel, Field

from cfn_auditor.rules import Severity

__all__ = ["HealthResponse", "RuleResponse"]


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
    severity: Severity
    resource_types: list[str] = Field(
        description="CloudFormation resource types the rule applies to, sorted."
    )
