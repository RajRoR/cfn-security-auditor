"""CFN_CT_001 — CloudTrail trail without KMSKeyId (pure absence check)."""

from cfn_auditor.rules import Severity
from cfn_auditor.rules.checks.cloudtrail import CloudTrailMissingKmsKeyId
from tests.rules._helpers import evaluate_first_resource

RULE = CloudTrailMissingKmsKeyId()


def test_pass_kms_key_present() -> None:
    """KMSKeyId present (literal) → no finding."""
    yaml_text = """\
Resources:
  Trail:
    Type: AWS::CloudTrail::Trail
    Properties:
      IsLogging: true
      S3BucketName: trail-bucket
      KMSKeyId: arn:aws:kms:us-east-1:123:key/abc
"""
    assert evaluate_first_resource(yaml_text, RULE) == []


def test_pass_kms_key_intrinsic_present() -> None:
    """KMSKeyId is an intrinsic — present is present, no finding."""
    yaml_text = """\
Resources:
  Trail:
    Type: AWS::CloudTrail::Trail
    Properties:
      IsLogging: true
      S3BucketName: trail-bucket
      KMSKeyId: !Ref KmsKeyParam
"""
    assert evaluate_first_resource(yaml_text, RULE) == []


def test_fail_kms_key_absent() -> None:
    """KMSKeyId absent → MEDIUM finding."""
    yaml_text = """\
Resources:
  Trail:
    Type: AWS::CloudTrail::Trail
    Properties:
      IsLogging: true
      S3BucketName: trail-bucket
"""
    findings = evaluate_first_resource(yaml_text, RULE)
    assert len(findings) == 1
    assert findings[0].severity is Severity.MEDIUM
    assert findings[0].rule_id == "CFN_CT_001"
