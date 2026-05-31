"""Streamlit dashboard for CFN Security Auditor.

Pure HTTP client of the FastAPI service. Run with::

    uv run streamlit run src/cfn_auditor/dashboard/app.py

This module is intentionally thin: every piece of logic that can be unit-
tested without a Streamlit runtime lives in :mod:`cfn_auditor.dashboard.client`.
"""

from __future__ import annotations

import logging

import pandas as pd
import streamlit as st

from cfn_auditor.dashboard.client import (
    DashboardClient,
    DashboardClientError,
    FindingRow,
    ScanDisplay,
    TrendPoint,
    build_findings_rows,
    build_scan_display,
    build_trend_series,
)

logger = logging.getLogger(__name__)


def _render_score_panel(display: ScanDisplay) -> None:
    """Score, grade, gate badge, and severity counts."""
    cols = st.columns(3)
    cols[0].metric("Score", f"{display.score} / 100")
    cols[1].metric("Grade", display.grade)
    badge = "✅ PASS" if display.passed else "❌ FAIL"
    cols[2].metric("Gate", badge)

    counts = st.columns(5)
    counts[0].metric("Critical", display.critical_count)
    counts[1].metric("High", display.high_count)
    counts[2].metric("Medium", display.medium_count)
    counts[3].metric("Low", display.low_count)
    counts[4].metric("Info", display.info_count)


def _render_findings_table(rows: list[FindingRow]) -> None:
    """Severity-coloured findings table."""
    if not rows:
        st.success("No findings — every guardrail passed.")
        return

    frame = pd.DataFrame(
        [
            {
                "id": r.id,
                "rule_id": r.rule_id,
                "severity": r.severity,
                "resource": r.resource,
                "message": r.message,
            }
            for r in rows
        ]
    )

    def _row_style(row: pd.Series) -> list[str]:
        color_map = {r.id: r.color for r in rows}
        colour = color_map.get(int(row["id"]), "#9e9e9e")
        return [f"background-color: {colour}; color: white;" for _ in row]

    st.dataframe(frame.style.apply(_row_style, axis=1), use_container_width=True)


def _render_trend(points: list[TrendPoint]) -> None:
    """Score-over-time chart."""
    if not points:
        st.info("No prior scans yet — your trend chart will populate here.")
        return
    frame = pd.DataFrame(
        [
            {
                "scan_id": p.scan_id,
                "created_at": p.created_at,
                "score": p.score,
            }
            for p in points
        ]
    )
    st.line_chart(frame.set_index("created_at")["score"])


def _surface_error(exc: DashboardClientError) -> None:
    """Map a ``DashboardClientError`` onto a clean Streamlit message."""
    if exc.status_code == 401:
        st.error(
            "API rejected the request: 401 Unauthorized. "
            "Set CFN_AUDITOR_API_KEY in the dashboard environment."
        )
    elif exc.status_code == 413:
        st.error("Template too large for the configured size limit.")
    elif exc.status_code == 400:
        st.error(f"API rejected the template: {exc.detail}")
    else:
        st.error(f"API error {exc.status_code}: {exc.detail}")


def main() -> None:  # pragma: no cover - Streamlit runtime entry point
    """Streamlit entry point."""
    st.set_page_config(page_title="CFN Security Auditor", layout="wide")
    st.title("CFN Security Auditor")
    st.caption("Static-analysis security guardrails for AWS CloudFormation templates.")

    with st.sidebar:
        st.header("New scan")
        name = st.text_input("Template label", value="template")
        uploaded = st.file_uploader("Upload a template", type=["yaml", "yml", "json"])
        pasted = st.text_area("…or paste here", height=240)
        run_button = st.button("Run scan", type="primary")

    template_text: str | None = None
    if uploaded is not None:
        template_text = uploaded.getvalue().decode("utf-8", errors="replace")
    elif pasted.strip():
        template_text = pasted

    if run_button:
        if not template_text:
            st.warning("Provide a template (upload or paste) before running a scan.")
        else:
            try:
                with DashboardClient() as client:
                    payload = client.post_scan(template_text, name=name or "template")
                    history = client.list_scans()
            except DashboardClientError as exc:
                _surface_error(exc)
            else:
                st.subheader("Latest scan")
                _render_score_panel(build_scan_display(payload))
                st.subheader("Findings")
                _render_findings_table(build_findings_rows(payload))
                st.subheader("Score trend")
                _render_trend(build_trend_series(history))
    else:
        try:
            with DashboardClient() as client:
                history = client.list_scans()
        except DashboardClientError as exc:
            _surface_error(exc)
        else:
            st.subheader("Recent scans")
            _render_trend(build_trend_series(history))


if __name__ == "__main__":  # pragma: no cover
    main()
