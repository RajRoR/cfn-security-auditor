"""S3-001 — AWS::S3::Bucket missing BucketEncryption.

Three cases, end-to-end via parse_template:
  * pass: BucketEncryption literal present → no finding
  * fail: BucketEncryption absent → finding
  * intrinsic: BucketEncryption is an !If → no finding (cannot assert insecurity)
"""

from cfn_auditor.parser import parse_template
from cfn_auditor.rules import RuleFinding, Severity
from cfn_auditor.rules.checks.s3 import S3MissingBucketEncryption


def _evaluate(yaml_text: str) -> list[RuleFinding]:
    """Parse ``yaml_text``, evaluate S3-001 against the first resource."""
    template = parse_template(yaml_text, "s3.yaml")
    rule = S3MissingBucketEncryption()
    return rule.evaluate(template.resources[0], template)


def test_s3_001_no_finding_when_encryption_literal_present() -> None:
    """Literal BucketEncryption block is compliant."""
    yaml_text = """\
Resources:
  Encrypted:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: encrypted
      BucketEncryption:
        ServerSideEncryptionConfiguration:
          - ServerSideEncryptionByDefault:
              SSEAlgorithm: AES256
"""
    assert _evaluate(yaml_text) == []


def test_s3_001_finding_when_encryption_absent() -> None:
    """Missing BucketEncryption raises a HIGH-severity finding."""
    yaml_text = """\
Resources:
  Bare:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: bare
"""
    findings = _evaluate(yaml_text)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.rule_id == "CFN_S3_001"
    assert finding.severity is Severity.HIGH
    assert finding.resource_logical_id == "Bare"
    assert "BucketEncryption" in finding.message
    assert finding.remediation


def test_s3_001_finding_when_properties_block_absent() -> None:
    """A bucket with no Properties at all is missing BucketEncryption."""
    yaml_text = """\
Resources:
  Naked:
    Type: AWS::S3::Bucket
"""
    findings = _evaluate(yaml_text)
    assert len(findings) == 1
    assert findings[0].rule_id == "CFN_S3_001"


def test_s3_001_no_finding_when_encryption_is_intrinsic() -> None:
    """!If on BucketEncryption means we cannot assert insecurity → no finding."""
    yaml_text = """\
Conditions:
  IsProd: !Equals [!Ref Env, prod]
Resources:
  Conditional:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: conditional
      BucketEncryption: !If
        - IsProd
        - ServerSideEncryptionConfiguration:
            - ServerSideEncryptionByDefault:
                SSEAlgorithm: AES256
        - !Ref AWS::NoValue
"""
    assert _evaluate(yaml_text) == []


def test_s3_001_no_finding_when_encryption_is_ref() -> None:
    """!Ref on BucketEncryption is also an unresolved intrinsic → no finding."""
    yaml_text = """\
Resources:
  RefBucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketEncryption: !Ref EncryptionConfigParam
"""
    assert _evaluate(yaml_text) == []


def test_s3_001_metadata_matches_contract() -> None:
    """Rule metadata matches the documented contract."""
    rule = S3MissingBucketEncryption()
    assert rule.id == "CFN_S3_001"
    assert rule.severity is Severity.HIGH
    assert rule.resource_types == frozenset({"AWS::S3::Bucket"})
    assert rule.title
