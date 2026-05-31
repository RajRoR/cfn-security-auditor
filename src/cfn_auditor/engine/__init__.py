"""Audit engine — orchestrates parse → run rules → persist."""

from cfn_auditor.engine.scanner import run_scan

__all__ = ["run_scan"]
