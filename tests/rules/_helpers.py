"""Shared helpers for per-rule tests in the rules batch."""

from cfn_auditor.parser import parse_template
from cfn_auditor.rules import Rule, RuleFinding


def evaluate_first_resource(yaml_text: str, rule: Rule) -> list[RuleFinding]:
    """Parse ``yaml_text`` and run ``rule`` against the first resource."""
    template = parse_template(yaml_text, "fixture.yaml")
    return rule.evaluate(template.resources[0], template)
