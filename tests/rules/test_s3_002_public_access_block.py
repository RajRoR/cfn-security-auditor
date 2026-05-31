"""CFN_S3_002 — PublicAccessBlockConfiguration missing or any flag literal-false."""

from cfn_auditor.rules import Severity
from cfn_auditor.rules.checks.s3 import S3MissingPublicAccessBlock
from cfn_auditor.rules.remediation import REMEDIATION_BY_RULE_ID
from tests.rules._helpers import evaluate_first_resource

RULE = S3MissingPublicAccessBlock()


def test_pass_all_flags_true() -> None:
    """All four flags literally true → no finding."""
    yaml_text = """\
Resources:
  Locked:
    Type: AWS::S3::Bucket
    Properties:
      PublicAccessBlockConfiguration:
        BlockPublicAcls: true
        IgnorePublicAcls: true
        BlockPublicPolicy: true
        RestrictPublicBuckets: true
"""
    assert evaluate_first_resource(yaml_text, RULE) == []


def test_fail_block_absent() -> None:
    """No PublicAccessBlockConfiguration → CRITICAL finding."""
    yaml_text = """\
Resources:
  Naked:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: naked
"""
    findings = evaluate_first_resource(yaml_text, RULE)
    assert len(findings) == 1
    assert findings[0].severity is Severity.CRITICAL
    assert findings[0].rule_id == "CFN_S3_002"


def test_fail_one_flag_false() -> None:
    """Any single flag literally false → finding mentioning that flag."""
    yaml_text = """\
Resources:
  Loose:
    Type: AWS::S3::Bucket
    Properties:
      PublicAccessBlockConfiguration:
        BlockPublicAcls: false
        IgnorePublicAcls: true
        BlockPublicPolicy: true
        RestrictPublicBuckets: true
"""
    findings = evaluate_first_resource(yaml_text, RULE)
    assert len(findings) == 1
    assert "BlockPublicAcls" in findings[0].message


def test_no_finding_when_block_is_intrinsic() -> None:
    """!If on the whole block → no finding (cannot assert insecurity)."""
    yaml_text = """\
Resources:
  Conditional:
    Type: AWS::S3::Bucket
    Properties:
      PublicAccessBlockConfiguration: !If
        - IsProd
        - BlockPublicAcls: true
          IgnorePublicAcls: true
          BlockPublicPolicy: true
          RestrictPublicBuckets: true
        - !Ref AWS::NoValue
"""
    assert evaluate_first_resource(yaml_text, RULE) == []


def test_no_finding_when_flag_is_intrinsic() -> None:
    """!Ref on a single flag → that flag does not fire."""
    yaml_text = """\
Resources:
  Refd:
    Type: AWS::S3::Bucket
    Properties:
      PublicAccessBlockConfiguration:
        BlockPublicAcls: !Ref ParamBlockAcls
        IgnorePublicAcls: true
        BlockPublicPolicy: true
        RestrictPublicBuckets: true
"""
    assert evaluate_first_resource(yaml_text, RULE) == []


def test_s3_002_remediation_is_path_agnostic() -> None:
    """Remediation reads correctly for both trigger paths.

    S3-002 fires on either (a) PublicAccessBlockConfiguration missing OR
    (b) any of the four flags literally false. The static remediation must
    cover both — no "Add ..." phrasing that implies only the missing-block
    path applies.
    """
    text = REMEDIATION_BY_RULE_ID["CFN_S3_002"]
    # Names every flag the rule inspects.
    for flag in (
        "BlockPublicAcls",
        "IgnorePublicAcls",
        "BlockPublicPolicy",
        "RestrictPublicBuckets",
    ):
        assert flag in text
    # Reads correctly when the block is already present (path b).
    assert "Ensure" in text or "Make sure" in text or "all four flags" in text
    # Does not lock the reader into the missing-block reading.
    assert not text.lower().startswith("add publicaccessblockconfiguration")
    # And both code-path findings expose the same string.
    missing_block_yaml = """\
Resources:
  R:
    Type: AWS::S3::Bucket
    Properties: {}
"""
    flag_false_yaml = """\
Resources:
  R:
    Type: AWS::S3::Bucket
    Properties:
      PublicAccessBlockConfiguration:
        BlockPublicAcls: false
        IgnorePublicAcls: true
        BlockPublicPolicy: true
        RestrictPublicBuckets: true
"""
    a = evaluate_first_resource(missing_block_yaml, RULE)
    b = evaluate_first_resource(flag_false_yaml, RULE)
    assert len(a) == 1 and len(b) == 1
    assert a[0].remediation == text
    assert b[0].remediation == text
