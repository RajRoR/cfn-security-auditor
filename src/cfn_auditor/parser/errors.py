"""Domain errors raised by the parser layer.

All errors derive from ``TemplateParseError`` so callers can catch a single
base. Messages never include sensitive data — they describe the *kind* of
problem, the template name, and a short reason; they never echo template
content.
"""

__all__ = [
    "MalformedTemplateError",
    "NotACloudFormationTemplateError",
    "TemplateParseError",
    "TemplateTooLargeError",
]


class TemplateParseError(Exception):
    """Base class for any parser-layer failure."""


class MalformedTemplateError(TemplateParseError):
    """The input is not valid YAML or JSON, or has an unsupported tag."""


class TemplateTooLargeError(TemplateParseError):
    """The input exceeds the configured maximum template size."""


class NotACloudFormationTemplateError(TemplateParseError):
    """The input is well-formed YAML/JSON but is not a CFN template."""
