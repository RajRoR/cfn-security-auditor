"""CFN_S3_003 — bucket AccessControl is PublicRead or PublicReadWrite."""

import pytest

from cfn_auditor.rules import Severity
from cfn_auditor.rules.checks.s3 import S3PublicAcl
from tests.rules._helpers import evaluate_first_resource

RULE = S3PublicAcl()


def test_pass_private_acl() -> None:
    """AccessControl literally Private → no finding."""
    yaml_text = """\
Resources:
  Private:
    Type: AWS::S3::Bucket
    Properties:
      AccessControl: Private
"""
    assert evaluate_first_resource(yaml_text, RULE) == []


def test_pass_no_acl() -> None:
    """No AccessControl → no finding (the ACL absence is a different rule)."""
    yaml_text = """\
Resources:
  Bare:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: bare
"""
    assert evaluate_first_resource(yaml_text, RULE) == []


@pytest.mark.parametrize("acl", ["PublicRead", "PublicReadWrite"])
def test_fail_public_acl_literal(acl: str) -> None:
    """Public canned ACLs fire CRITICAL."""
    yaml_text = f"""\
Resources:
  Open:
    Type: AWS::S3::Bucket
    Properties:
      AccessControl: {acl}
"""
    findings = evaluate_first_resource(yaml_text, RULE)
    assert len(findings) == 1
    assert findings[0].severity is Severity.CRITICAL
    assert acl in findings[0].message


def test_no_finding_when_acl_is_intrinsic() -> None:
    """!Ref on AccessControl → no finding."""
    yaml_text = """\
Resources:
  Refd:
    Type: AWS::S3::Bucket
    Properties:
      AccessControl: !Ref AclParam
"""
    assert evaluate_first_resource(yaml_text, RULE) == []
