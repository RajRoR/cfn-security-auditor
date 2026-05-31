"""Guardrail rule registry and public surface.

Importing this package eagerly imports every check module, which is what
populates the registry. Consumers should never import individual check
modules directly — go through :func:`all_rules`.
"""

from cfn_auditor.rules import checks  # noqa: F401  (side-effect: registers rules)
from cfn_auditor.rules.base import Rule
from cfn_auditor.rules.finding import RuleFinding
from cfn_auditor.rules.intrinsics import as_list, is_intrinsic, literal_or_none
from cfn_auditor.rules.registry import all_rules, register
from cfn_auditor.rules.severity import Severity

__all__ = [
    "Rule",
    "RuleFinding",
    "Severity",
    "all_rules",
    "as_list",
    "is_intrinsic",
    "literal_or_none",
    "register",
]
