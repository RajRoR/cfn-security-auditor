"""Framework tests: RuleFinding DTO, Severity, Rule base, registry, intrinsics."""

from dataclasses import FrozenInstanceError
from typing import ClassVar

import pytest

from cfn_auditor.parser import Resource, Template
from cfn_auditor.rules import (
    Rule,
    RuleFinding,
    Severity,
    is_intrinsic,
    literal_or_none,
    register,
)
from cfn_auditor.rules.registry import all_rules


def _empty_template() -> Template:
    return Template(name="t.yaml", description=None, resources=(), raw={})


def _resource(logical_id: str, type_: str, properties: dict[str, object]) -> Resource:
    return Resource(
        logical_id=logical_id,
        type=type_,
        properties=properties,
        raw={"Type": type_, "Properties": properties},
    )


def test_severity_values_match_persisted_enum() -> None:
    """Severity enum values are the canonical CRITICAL/HIGH/MEDIUM/LOW strings."""
    assert {s.value for s in Severity} == {"CRITICAL", "HIGH", "MEDIUM", "LOW"}


def test_rule_finding_is_frozen_dto() -> None:
    """RuleFinding is immutable and exposes the documented attributes."""
    finding = RuleFinding(
        rule_id="X",
        severity=Severity.HIGH,
        resource_logical_id="R",
        message="m",
        remediation="r",
    )
    with pytest.raises(FrozenInstanceError):
        finding.rule_id = "Y"  # type: ignore[misc]


def test_register_appends_to_all_rules() -> None:
    """@register makes the rule visible via all_rules() and survives re-registration tests."""
    before = {r.id for r in all_rules()}
    assert "CFN_S3_001" in before


def test_register_rejects_duplicate_id() -> None:
    """Registering two rules with the same id raises ValueError."""

    class _Dup(Rule):
        id: ClassVar[str] = "CFN_S3_001"
        title: ClassVar[str] = "duplicate"
        severity: ClassVar[Severity] = Severity.LOW
        resource_types: ClassVar[frozenset[str]] = frozenset({"AWS::S3::Bucket"})

        def evaluate(self, resource: Resource, template: Template) -> list[RuleFinding]:
            return []

    with pytest.raises(ValueError, match="Duplicate rule id"):
        register(_Dup)


def test_rule_base_class_is_abstract() -> None:
    """Rule cannot be instantiated without implementing evaluate."""
    with pytest.raises(TypeError):
        Rule()  # type: ignore[abstract]


def test_concrete_rule_evaluates() -> None:
    """A concrete subclass evaluates a resource and returns RuleFinding instances."""

    class _CountingRule(Rule):
        id: ClassVar[str] = "CFN_TEST_PROBE"
        title: ClassVar[str] = "probe"
        severity: ClassVar[Severity] = Severity.MEDIUM
        resource_types: ClassVar[frozenset[str]] = frozenset({"AWS::Test::Probe"})

        def evaluate(self, resource: Resource, template: Template) -> list[RuleFinding]:
            return [
                RuleFinding(
                    rule_id=self.id,
                    severity=self.severity,
                    resource_logical_id=resource.logical_id,
                    message="m",
                    remediation="r",
                )
            ]

    rule = _CountingRule()
    findings = rule.evaluate(
        _resource("R", "AWS::Test::Probe", {}),
        _empty_template(),
    )
    assert len(findings) == 1
    assert findings[0].rule_id == "CFN_TEST_PROBE"


@pytest.mark.parametrize(
    "value",
    [
        {"Ref": "X"},
        {"Fn::GetAtt": ["A", "B"]},
        {"Fn::If": ["C", "a", "b"]},
        {"Fn::Sub": "${X}"},
        {"Condition": "Cond"},
    ],
)
def test_is_intrinsic_true_for_intrinsic_dicts(value: dict[str, object]) -> None:
    """Single-key dicts whose key is a CFN intrinsic are intrinsics."""
    assert is_intrinsic(value) is True
    assert literal_or_none(value) is None


@pytest.mark.parametrize(
    "value",
    [
        "literal",
        42,
        True,
        ["a", "b"],
        {"Foo": "bar"},
        {"Ref": "X", "Other": 1},  # two keys: not an intrinsic
        {},
    ],
)
def test_is_intrinsic_false_for_non_intrinsic_values(value: object) -> None:
    """Scalars, lists, and multi-key dicts are not intrinsics."""
    assert is_intrinsic(value) is False
    assert literal_or_none(value) == value


def test_literal_or_none_is_shallow() -> None:
    """A literal whose nested children are intrinsics is still returned as-is."""
    nested = {"Top": {"Ref": "Inner"}}
    assert literal_or_none(nested) == nested
