"""Pure transform tests: severity colours, findings projection, trend ordering."""

import pytest

from cfn_auditor.dashboard.client import (
    SEVERITY_COLORS,
    build_findings_rows,
    build_scan_display,
    build_trend_series,
    severity_color,
)

CRITICAL_PAYLOAD = {
    "id": 1,
    "template_name": "critical.yaml",
    "status": "SUCCEEDED",
    "finding_count": 3,
    "critical_count": 1,
    "high_count": 1,
    "medium_count": 1,
    "low_count": 0,
    "info_count": 0,
    "score": {"score": 30, "grade": "F", "passed": False},
    "findings": [
        {
            "id": 11,
            "rule_id": "CFN_S3_001",
            "severity": "HIGH",
            "resource_logical_id": "Bucket",
            "resource_type": "AWS::S3::Bucket",
            "message": "S3 bucket has no encryption.",
        },
        {
            "id": 12,
            "rule_id": "CFN_RDS_002",
            "severity": "CRITICAL",
            "resource_logical_id": "Db",
            "resource_type": "AWS::RDS::DBInstance",
            "message": "DB is publicly accessible.",
        },
        {
            "id": 13,
            "rule_id": "CFN_CT_001",
            "severity": "MEDIUM",
            "resource_logical_id": "Trail",
            "resource_type": "AWS::CloudTrail::Trail",
            "message": "Trail has no KMSKeyId.",
        },
    ],
}


def test_severity_color_known_levels_match_palette() -> None:
    """Every documented severity has a colour in the palette."""
    for severity, expected in SEVERITY_COLORS.items():
        assert severity_color(severity) == expected


def test_severity_color_unknown_falls_back_to_grey() -> None:
    """Unknown severities still render — they don't crash the table."""
    assert severity_color("WAT") == "#9e9e9e"


def test_build_findings_rows_orders_critical_first() -> None:
    """Findings sort CRITICAL → HIGH → MEDIUM → LOW → INFO, then by rule_id, then resource."""
    rows = build_findings_rows(CRITICAL_PAYLOAD)
    assert [r.severity for r in rows] == ["CRITICAL", "HIGH", "MEDIUM"]
    assert [r.rule_id for r in rows] == ["CFN_RDS_002", "CFN_S3_001", "CFN_CT_001"]
    assert rows[0].color == SEVERITY_COLORS["CRITICAL"]
    assert rows[1].color == SEVERITY_COLORS["HIGH"]


def test_build_findings_rows_handles_empty_payload() -> None:
    """A scan with no findings yields an empty list."""
    payload = {**CRITICAL_PAYLOAD, "findings": []}
    assert build_findings_rows(payload) == []


def test_build_scan_display_extracts_score_envelope() -> None:
    """The score envelope is unpacked onto the display dataclass."""
    display = build_scan_display(CRITICAL_PAYLOAD)
    assert display.id == 1
    assert display.score == 30
    assert display.grade == "F"
    assert display.passed is False
    assert display.critical_count == 1


def test_build_trend_series_oldest_first_with_id_tiebreak() -> None:
    """Trend series sorts by created_at ascending; equal timestamps break by id."""
    history = [
        {
            "id": 3,
            "created_at": "2026-05-31T10:02:00Z",
            "template_name": "t",
            "status": "SUCCEEDED",
            "finding_count": 0,
            "critical_count": 0,
            "high_count": 0,
            "medium_count": 0,
            "low_count": 0,
            "info_count": 0,
            "score": {"score": 100, "grade": "A", "passed": True},
        },
        {
            "id": 1,
            "created_at": "2026-05-31T10:00:00Z",
            "template_name": "t",
            "status": "SUCCEEDED",
            "finding_count": 4,
            "critical_count": 0,
            "high_count": 1,
            "medium_count": 3,
            "low_count": 0,
            "info_count": 0,
            "score": {"score": 50, "grade": "F", "passed": True},
        },
        {
            "id": 2,
            "created_at": "2026-05-31T10:00:00Z",
            "template_name": "t",
            "status": "SUCCEEDED",
            "finding_count": 8,
            "critical_count": 4,
            "high_count": 3,
            "medium_count": 1,
            "low_count": 0,
            "info_count": 0,
            "score": {"score": 0, "grade": "F", "passed": False},
        },
    ]
    series = build_trend_series(history)
    assert [p.scan_id for p in series] == [1, 2, 3]
    assert [p.score for p in series] == [50, 0, 100]


def test_build_trend_series_empty_history() -> None:
    """Empty history yields an empty series."""
    assert build_trend_series([]) == []


@pytest.mark.parametrize(
    "severity",
    ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"],
)
def test_palette_contains_documented_severities(severity: str) -> None:
    """The palette covers every severity the API can return."""
    assert severity in SEVERITY_COLORS
