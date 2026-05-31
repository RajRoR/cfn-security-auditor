"""Pure unit tests for cfn_auditor.scoring.

Three groups:
  1. Oracle expectations — clean / medium / critical from the engine turn.
  2. Grade-band boundary tests (89/90, 79/80, 69/70, 59/60).
  3. Gate semantics — one CRITICAL flips passed False; many lower-severity
     findings with zero CRITICALs stay passed True.
"""

import pytest

from cfn_auditor.models import Severity
from cfn_auditor.scoring import (
    GRADE_BANDS,
    PENALTY_WEIGHTS,
    ScoreResult,
    score,
)


def _counts(
    critical: int = 0,
    high: int = 0,
    medium: int = 0,
    low: int = 0,
    info: int = 0,
) -> dict[Severity, int]:
    """Compose a severity-count mapping with the named buckets."""
    return {
        Severity.CRITICAL: critical,
        Severity.HIGH: high,
        Severity.MEDIUM: medium,
        Severity.LOW: low,
        Severity.INFO: info,
    }


# ---------------------------------------------------------------------------
# Locked weight contract
# ---------------------------------------------------------------------------


def test_penalty_weights_are_locked() -> None:
    """The weights are the documented contract; do not tune without a prompt."""
    assert PENALTY_WEIGHTS[Severity.CRITICAL] == 40
    assert PENALTY_WEIGHTS[Severity.HIGH] == 20
    assert PENALTY_WEIGHTS[Severity.MEDIUM] == 10
    assert PENALTY_WEIGHTS[Severity.LOW] == 3
    assert PENALTY_WEIGHTS[Severity.INFO] == 0


def test_score_result_is_frozen() -> None:
    """ScoreResult is immutable."""
    from dataclasses import FrozenInstanceError

    result = score(_counts())
    with pytest.raises(FrozenInstanceError):
        result.score = 0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Oracle expectations (from the engine turn fixtures)
# ---------------------------------------------------------------------------


def test_clean_oracle_scores_perfect() -> None:
    """Zero findings → 100 / A / passed."""
    result = score(_counts())
    assert result == ScoreResult(score=100, grade="A", passed=True)


def test_medium_oracle() -> None:
    """1 HIGH (20) + 3 MEDIUM (30) → score 50, grade F, passed True (no CRITICALs)."""
    result = score(_counts(high=1, medium=3))
    assert result.score == 50
    assert result.grade == "F"
    assert result.passed is True


def test_critical_oracle() -> None:
    """4 CRITICAL (160) + 3 HIGH (60) + 1 MEDIUM (10) → clamped 0, F, passed False."""
    result = score(_counts(critical=4, high=3, medium=1))
    assert result.score == 0
    assert result.grade == "F"
    assert result.passed is False


# ---------------------------------------------------------------------------
# Grade-band boundaries (89/90, 79/80, 69/70, 59/60)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("counts_kwargs", "expected_score", "expected_grade"),
    [
        # 90 -> A; 89 -> B
        ({"medium": 1}, 90, "A"),
        ({"low": 3, "medium": 0}, 91, "A"),
        ({"medium": 1, "low": 1}, 87, "B"),
        # 80 -> B; 79 -> C
        ({"high": 1}, 80, "B"),
        ({"medium": 2, "low": 0}, 80, "B"),
        ({"high": 1, "low": 1}, 77, "C"),
        # 70 -> C; 69 -> D
        ({"high": 1, "medium": 1}, 70, "C"),
        ({"high": 1, "medium": 1, "low": 1}, 67, "D"),
        # 60 -> D; 59 -> F
        ({"high": 2}, 60, "D"),
        ({"high": 2, "low": 1}, 57, "F"),
    ],
)
def test_grade_band_boundaries(
    counts_kwargs: dict[str, int],
    expected_score: int,
    expected_grade: str,
) -> None:
    """Inclusive lower bounds: each band's floor is the lower grade boundary."""
    result = score(_counts(**counts_kwargs))
    assert result.score == expected_score
    assert result.grade == expected_grade


def test_grade_bands_are_locked() -> None:
    """The grade-band table is the documented contract."""
    assert GRADE_BANDS == ((90, "A"), (80, "B"), (70, "C"), (60, "D"))


# ---------------------------------------------------------------------------
# Gate semantics
# ---------------------------------------------------------------------------


def test_single_critical_fails_gate_even_at_otherwise_high_score() -> None:
    """One CRITICAL alone → score 60 (D), but gate fails."""
    result = score(_counts(critical=1))
    assert result.score == 60
    assert result.grade == "D"
    assert result.passed is False


def test_zero_criticals_with_many_findings_still_passes_gate() -> None:
    """Zero CRITICAL with HIGH/MEDIUM/LOW findings → gate still passes."""
    result = score(_counts(high=2, medium=5, low=10))
    assert result.passed is True
    # And it's a hard score regardless — gate is independent.
    assert result.score == 0
    assert result.grade == "F"


def test_score_is_clamped_at_zero() -> None:
    """Heavy findings clamp at zero, not negative."""
    result = score(_counts(critical=10))
    assert result.score == 0


def test_missing_keys_treated_as_zero() -> None:
    """A counts mapping with only some severities populated still works."""
    result = score({Severity.HIGH: 1})
    assert result.score == 80
    assert result.grade == "B"
    assert result.passed is True


def test_negative_count_raises() -> None:
    """Negative counts are a programming error; surface them loudly."""
    with pytest.raises(ValueError, match="non-negative"):
        score(_counts(critical=-1))
