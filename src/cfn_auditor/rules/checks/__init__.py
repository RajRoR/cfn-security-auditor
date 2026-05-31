"""Concrete guardrail rules.

Importing this package triggers each check module's ``@register`` calls. An
unimported service module silently fails to register its rules, so this
``__init__`` is the single source of truth for which rules are live.
"""

from cfn_auditor.rules.checks import (  # noqa: F401  (side-effect imports)
    cloudtrail,
    ec2,
    iam,
    rds,
    s3,
    sg,
)

__all__: list[str] = []
