"""Deterministic scoring: severity counts → score, letter grade, gate decision.

Pure, side-effect-free function. This module is a leaf — it imports only
:class:`cfn_auditor.models.Severity` and the standard library. Nothing here
touches the engine, the database, or any I/O.

Penalty weights (locked contract — do not tune without an explicit prompt):

  ============  ======
  Severity      Weight
  ============  ======
  CRITICAL      40
  HIGH          20
  MEDIUM        10
  LOW            3
  INFO           0
  ============  ======

Score formula: ``score = max(0, 100 - sum(weight * count))``. Always an integer.

Letter-grade bands (inclusive lower bounds):

  =====  ===========
  Grade  Score range
  =====  ===========
  A      >= 90
  B      80 - 89
  C      70 - 79
  D      60 - 69
  F      < 60
  =====  ===========

Gate semantics
--------------
``passed = (critical_count == 0)``. The pre-deploy gate fails on any single
CRITICAL finding regardless of the numeric score; the score and grade are
informational. Score is **not** part of the gate this turn — one gate rule,
explicitly stated.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from cfn_auditor.models import Severity

__all__ = ["GRADE_BANDS", "PENALTY_WEIGHTS", "ScoreResult", "score"]


PENALTY_WEIGHTS: Final[Mapping[Severity, int]] = {
    Severity.CRITICAL: 40,
    Severity.HIGH: 20,
    Severity.MEDIUM: 10,
    Severity.LOW: 3,
    Severity.INFO: 0,
}

# (lower_bound, grade). Iterated in order; the first match wins.
GRADE_BANDS: Final[tuple[tuple[int, str], ...]] = (
    (90, "A"),
    (80, "B"),
    (70, "C"),
    (60, "D"),
)


@dataclass(frozen=True)
class ScoreResult:
    """Result of scoring a scan's severity counts.

    Attributes:
        score: Integer in ``[0, 100]``.
        grade: Letter grade — one of ``"A"``, ``"B"``, ``"C"``, ``"D"``, ``"F"``.
        passed: ``True`` if the scan passes the pre-deploy gate
            (``critical_count == 0``); ``False`` otherwise.
    """

    score: int
    grade: str
    passed: bool


def score(counts: Mapping[Severity, int]) -> ScoreResult:
    """Compute the score, grade, and gate decision from severity counts.

    Args:
        counts: Mapping of :class:`Severity` to non-negative count. Missing
            severities are treated as zero. Extra keys raise ``KeyError`` —
            the caller has handed us something unexpected.

    Returns:
        A :class:`ScoreResult`.

    Raises:
        ValueError: If any count is negative.
    """
    for severity, count in counts.items():
        if count < 0:
            raise ValueError(f"Severity counts must be non-negative; {severity.value}={count}.")

    penalty = sum(PENALTY_WEIGHTS[sev] * counts.get(sev, 0) for sev in Severity)
    raw = 100 - penalty
    final_score = max(0, raw)
    grade = _grade_for(final_score)
    passed = counts.get(Severity.CRITICAL, 0) == 0
    return ScoreResult(score=final_score, grade=grade, passed=passed)


def _grade_for(numeric_score: int) -> str:
    """Map an integer score in ``[0, 100]`` to a letter grade per ``GRADE_BANDS``."""
    for lower_bound, letter in GRADE_BANDS:
        if numeric_score >= lower_bound:
            return letter
    return "F"
