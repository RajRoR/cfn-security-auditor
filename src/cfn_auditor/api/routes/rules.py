"""Guardrail-rule listing endpoint. Reads from the in-process registry."""

from fastapi import APIRouter, Depends

from cfn_auditor.api.dependencies import require_api_key
from cfn_auditor.api.schemas import RuleResponse
from cfn_auditor.rules import all_rules

__all__ = ["router"]

router = APIRouter(tags=["rules"], dependencies=[Depends(require_api_key)])


@router.get("/rules", response_model=list[RuleResponse])
def list_rules() -> list[RuleResponse]:
    """Return every registered rule's public metadata, in registration order."""
    return [
        RuleResponse(
            id=rule.id,
            title=rule.title,
            severity=rule.severity,
            resource_types=sorted(rule.resource_types),
        )
        for rule in all_rules()
    ]
