"""Top-level template parser entry point.

``parse_template`` is the only function consumers should call. It enforces the
input-size cap, decodes bytes, runs the CFN-aware safe loader, and returns the
normalised :class:`~cfn_auditor.parser.model.Template` model.
"""

import logging
from typing import Any

import yaml

from cfn_auditor.config import get_settings
from cfn_auditor.parser.errors import (
    MalformedTemplateError,
    NotACloudFormationTemplateError,
    TemplateTooLargeError,
)
from cfn_auditor.parser.loader import safe_load
from cfn_auditor.parser.model import Resource, Template

__all__ = ["parse_template"]

logger = logging.getLogger(__name__)


def parse_template(content: str | bytes, name: str) -> Template:
    """Parse a CloudFormation template (YAML or JSON) into the domain model.

    Args:
        content: Raw template text, either a ``str`` or UTF-8 ``bytes``.
        name: Caller-supplied label (typically a filename) used in diagnostics.

    Returns:
        A :class:`Template` with short-form intrinsics normalised to full-form.

    Raises:
        TemplateTooLargeError: ``content`` exceeds ``settings.max_template_bytes``.
        MalformedTemplateError: ``content`` is not valid YAML or JSON.
        NotACloudFormationTemplateError: parsed content is structurally not CFN.
    """
    raw_bytes = content.encode("utf-8") if isinstance(content, str) else content
    cap = get_settings().max_template_bytes
    if len(raw_bytes) > cap:
        raise TemplateTooLargeError(
            f"{name}: template size {len(raw_bytes)} bytes exceeds limit of {cap} bytes."
        )

    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise MalformedTemplateError(f"{name}: template is not valid UTF-8.") from exc

    try:
        parsed = safe_load(text)
    except yaml.YAMLError as exc:
        raise MalformedTemplateError(
            f"{name}: invalid YAML/JSON ({exc.__class__.__name__})."
        ) from exc

    return _build_template(parsed, name)


def _build_template(parsed: Any, name: str) -> Template:
    """Validate the parsed structure and assemble a :class:`Template`."""
    if parsed is None:
        raise NotACloudFormationTemplateError(f"{name}: empty template.")
    if not isinstance(parsed, dict):
        raise NotACloudFormationTemplateError(
            f"{name}: top-level must be a mapping, got {type(parsed).__name__}."
        )

    resources_raw = parsed.get("Resources")
    if not isinstance(resources_raw, dict) or not resources_raw:
        raise NotACloudFormationTemplateError(f"{name}: missing or empty Resources mapping.")

    resources: list[Resource] = []
    for logical_id, raw_resource in resources_raw.items():
        if not isinstance(logical_id, str):
            raise NotACloudFormationTemplateError(
                f"{name}: resource logical id must be a string, got {type(logical_id).__name__}."
            )
        if not isinstance(raw_resource, dict):
            raise NotACloudFormationTemplateError(
                f"{name}: resource '{logical_id}' must be a mapping."
            )
        resource_type = raw_resource.get("Type")
        if not isinstance(resource_type, str) or not resource_type:
            raise NotACloudFormationTemplateError(
                f"{name}: resource '{logical_id}' is missing a Type."
            )
        properties = raw_resource.get("Properties", {})
        if properties is None:
            properties = {}
        if not isinstance(properties, dict):
            raise NotACloudFormationTemplateError(
                f"{name}: resource '{logical_id}' Properties must be a mapping."
            )
        resources.append(
            Resource(
                logical_id=logical_id,
                type=resource_type,
                properties=properties,
                raw=raw_resource,
            )
        )

    description = parsed.get("Description")
    if description is not None and not isinstance(description, str):
        description = None

    logger.debug("Parsed template %s with %d resources", name, len(resources))
    return Template(
        name=name,
        description=description,
        resources=tuple(resources),
        raw=parsed,
    )
