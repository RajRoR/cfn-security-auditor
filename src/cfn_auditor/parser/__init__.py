"""CloudFormation template parser (YAML/JSON → normalised domain model)."""

from cfn_auditor.parser.errors import (
    MalformedTemplateError,
    NotACloudFormationTemplateError,
    TemplateParseError,
    TemplateTooLargeError,
)
from cfn_auditor.parser.model import Resource, Template
from cfn_auditor.parser.parse import parse_template

__all__ = [
    "MalformedTemplateError",
    "NotACloudFormationTemplateError",
    "Resource",
    "Template",
    "TemplateParseError",
    "TemplateTooLargeError",
    "parse_template",
]
