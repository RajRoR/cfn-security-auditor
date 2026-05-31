"""Concrete guardrail rules.

Importing this package triggers each check module's ``@register`` calls.
"""

from cfn_auditor.rules.checks import s3  # noqa: F401 - registers rules

__all__: list[str] = []
