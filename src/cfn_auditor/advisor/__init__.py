"""AI Remediation Advisor — pluggable provider surface.

This module ships only the deterministic :class:`StaticRemediationProvider`
this PR. The LLM provider lands in part 2; the factory leaves a clear
seam for it.

Layering: the advisor may import :mod:`cfn_auditor.rules` (it reads the
canonical rule_id → remediation map). The reverse must NOT happen — rules
never import the advisor.
"""

from cfn_auditor.advisor.dto import AdviceItem, FindingInput
from cfn_auditor.advisor.provider import RemediationProvider, get_provider
from cfn_auditor.advisor.static import StaticRemediationProvider

__all__ = [
    "AdviceItem",
    "FindingInput",
    "RemediationProvider",
    "StaticRemediationProvider",
    "get_provider",
]
