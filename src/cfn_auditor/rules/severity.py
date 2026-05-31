"""Severity levels assigned to rule findings.

Defined here (not in ``models``) because the rules layer must not import the
db/models layer. The engine (later turn) maps this enum onto the persisted
``Finding.severity`` column.
"""

from enum import StrEnum

__all__ = ["Severity"]


class Severity(StrEnum):
    """Severity assigned to a rule finding. No numeric weights — that's scoring."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
