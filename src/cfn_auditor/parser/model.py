"""Normalised in-memory domain model for a parsed CloudFormation template.

These are plain DTOs (``dataclass``); they are **not** persisted. Rules consume
them directly. Keep this layer free of any DB / API concerns.
"""

from dataclasses import dataclass, field
from typing import Any

__all__ = ["Resource", "Template"]


@dataclass(frozen=True)
class Resource:
    """A single CloudFormation resource entry.

    Attributes:
        logical_id: The key under ``Resources`` in the source template.
        type: The CFN resource type, e.g. ``AWS::S3::Bucket``.
        properties: The resource ``Properties`` mapping. Short-form intrinsics
            in the source have already been normalised to full-form dicts
            (e.g. ``!Ref X`` → ``{"Ref": "X"}``).
        raw: The raw resource dict as parsed (before properties was extracted).
            Useful for rules that need to inspect non-Properties fields such as
            ``DeletionPolicy`` or ``UpdateReplacePolicy``.
    """

    logical_id: str
    type: str
    properties: dict[str, Any]
    raw: dict[str, Any]


@dataclass(frozen=True)
class Template:
    """A parsed CloudFormation template.

    Attributes:
        name: Caller-supplied label (typically a filename) for diagnostics.
        description: The template ``Description`` field, if any.
        resources: Resources in source order.
        raw: The full top-level dict as parsed (with intrinsics normalised).
    """

    name: str
    description: str | None
    resources: tuple[Resource, ...]
    raw: dict[str, Any] = field(default_factory=dict)

    def resource(self, logical_id: str) -> Resource:
        """Return the resource with ``logical_id`` or raise ``KeyError``."""
        for r in self.resources:
            if r.logical_id == logical_id:
                return r
        raise KeyError(logical_id)
