"""CloudFormation-aware YAML safe loader.

Subclasses :class:`yaml.SafeLoader` and registers constructors for every
CloudFormation short-form intrinsic. Each short tag is normalised into its
full-form dict (``!Ref X`` → ``{"Ref": "X"}``) so downstream code only ever
sees the canonical CFN data shape.

The project's security contract: use ``yaml.safe_load``, or ``yaml.load`` only
with an explicit ``SafeLoader`` subclass (this module's :class:`CfnSafeLoader`).
Never the default/Full/Unsafe loader.

Unknown ``!Tag`` values do **not** abort the parse — an auditor that refuses to
scan a template because it contains one exotic intrinsic is the wrong failure
mode. The fallback constructor preserves the unrecognised tag as opaque data
keyed by the tag name (e.g. ``{"!FutureFn": <node value>}``) and emits a
warning. Specific constructors registered above always take precedence.

References:
  - https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/intrinsic-function-reference.html
"""

import logging
from typing import Any

import yaml

__all__ = ["CfnSafeLoader", "safe_load"]

logger = logging.getLogger(__name__)


# Short tag → full-form key. Tags without an "Fn::" prefix (Ref, Condition)
# are kept as their bare name; everything else is wrapped under "Fn::".
_SHORT_TO_FULL: dict[str, str] = {
    "!Ref": "Ref",
    "!Condition": "Condition",
    "!GetAtt": "Fn::GetAtt",
    "!Sub": "Fn::Sub",
    "!Join": "Fn::Join",
    "!Select": "Fn::Select",
    "!Split": "Fn::Split",
    "!GetAZs": "Fn::GetAZs",
    "!ImportValue": "Fn::ImportValue",
    "!Base64": "Fn::Base64",
    "!Cidr": "Fn::Cidr",
    "!FindInMap": "Fn::FindInMap",
    "!If": "Fn::If",
    "!And": "Fn::And",
    "!Or": "Fn::Or",
    "!Not": "Fn::Not",
    "!Equals": "Fn::Equals",
    "!Transform": "Fn::Transform",
    "!Length": "Fn::Length",
    "!ToJsonString": "Fn::ToJsonString",
}


class CfnSafeLoader(yaml.SafeLoader):
    """YAML safe loader that understands CloudFormation short-form tags."""


def _node_value(loader: yaml.SafeLoader, node: yaml.Node) -> Any:
    """Construct the underlying value of a YAML node using safe constructors."""
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node, deep=True)
    if isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node, deep=True)
    raise yaml.constructor.ConstructorError(  # pragma: no cover - defensive
        None, None, "Unsupported YAML node kind", node.start_mark
    )


def _construct_intrinsic(full_key: str) -> Any:
    """Build a constructor that maps a known short tag to ``{full_key: value}``."""

    def constructor(loader: yaml.SafeLoader, node: yaml.Node) -> dict[str, Any]:
        value = _node_value(loader, node)
        # !GetAtt's scalar form uses dotted notation; CFN canonicalises to a
        # 2-element list of [logical_id, remaining-attribute-path].
        if full_key == "Fn::GetAtt" and isinstance(value, str):
            head, _, tail = value.partition(".")
            value = [head, tail]
        return {full_key: value}

    return constructor


def _construct_unknown(loader: yaml.SafeLoader, tag_suffix: str, node: yaml.Node) -> dict[str, Any]:
    """Fallback for any ``!Tag`` not in the known short-tag set.

    Preserves the tag name and the node value as opaque data so the parse can
    continue. A warning is logged once per occurrence so operators see the tag
    surfaced without it blocking the scan.
    """
    tag = f"!{tag_suffix}"
    logger.warning("Unknown CloudFormation short-form tag %r; preserving as opaque value.", tag)
    return {tag: _node_value(loader, node)}


for short, full in _SHORT_TO_FULL.items():
    CfnSafeLoader.add_constructor(short, _construct_intrinsic(full))

# Fallback for any unrecognised "!" tag. PyYAML resolves specific tag
# constructors before this multi-constructor, so the known tags above still win.
CfnSafeLoader.add_multi_constructor("!", _construct_unknown)  # type: ignore[no-untyped-call]


def safe_load(content: str) -> Any:
    """Safe-load YAML/JSON content with CloudFormation short-tag support."""
    return yaml.load(content, Loader=CfnSafeLoader)  # noqa: S506 - subclass of SafeLoader
