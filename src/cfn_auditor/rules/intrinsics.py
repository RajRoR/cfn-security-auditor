"""Helpers for handling unresolved CloudFormation intrinsics.

We do not evaluate ``Ref``/``Fn::*``/``Condition`` — the parser normalises
short tags to full-form dicts and leaves them as-is. Rules therefore see a
mix of literals and intrinsic dicts and must distinguish them before
asserting "this value is insecure."

Rule semantics agreed with the standing contract:
  * Absence checks fire on a missing property regardless.
  * Insecure-literal checks fire ONLY on the literal insecure value.
  * When a property is present but its value is an unresolved intrinsic, no
    finding is emitted — we cannot prove it is insecure.
"""

from typing import Any

__all__ = ["INTRINSIC_KEYS", "is_intrinsic", "literal_or_none"]


# Keys that, when sole top-level keys of a one-key dict, mark that dict as an
# unresolved CloudFormation intrinsic rather than user data. ``Condition`` is
# included because rules reference it via ``{"Condition": "Name"}``.
INTRINSIC_KEYS: frozenset[str] = frozenset(
    {
        "Ref",
        "Condition",
        "Fn::GetAtt",
        "Fn::Sub",
        "Fn::Join",
        "Fn::Select",
        "Fn::Split",
        "Fn::GetAZs",
        "Fn::ImportValue",
        "Fn::Base64",
        "Fn::Cidr",
        "Fn::FindInMap",
        "Fn::If",
        "Fn::And",
        "Fn::Or",
        "Fn::Not",
        "Fn::Equals",
        "Fn::Transform",
        "Fn::Length",
        "Fn::ToJsonString",
    }
)


def is_intrinsic(value: Any) -> bool:
    """Return True if ``value`` is an unresolved CloudFormation intrinsic dict."""
    if not isinstance(value, dict) or len(value) != 1:
        return False
    (only_key,) = value.keys()
    return only_key in INTRINSIC_KEYS


def literal_or_none(value: Any) -> Any:
    """Return ``value`` if it is a literal, else ``None`` for an intrinsic.

    A "literal" is anything that is not an unresolved intrinsic dict — this
    includes scalars (``str``, ``bool``, ``int``, ``float``), lists, and
    dicts whose sole top-level key is **not** an intrinsic key.

    The check is shallow on purpose: a property that is itself a literal but
    whose nested children include intrinsics is still returned. Rules that
    inspect nested values must decide per-leaf.
    """
    if is_intrinsic(value):
        return None
    return value
