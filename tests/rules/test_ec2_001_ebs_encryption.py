"""CFN_EC2_001 — EBS volume with Encrypted false or absent."""

from cfn_auditor.rules import Severity
from cfn_auditor.rules.checks.ec2 import EbsVolumeNotEncrypted
from tests.rules._helpers import evaluate_first_resource

RULE = EbsVolumeNotEncrypted()


def test_pass_encrypted_true() -> None:
    """Encrypted literally true → no finding."""
    yaml_text = """\
Resources:
  Vol:
    Type: AWS::EC2::Volume
    Properties:
      AvailabilityZone: us-east-1a
      Size: 20
      Encrypted: true
"""
    assert evaluate_first_resource(yaml_text, RULE) == []


def test_fail_encrypted_false() -> None:
    """Encrypted literally false → MEDIUM finding."""
    yaml_text = """\
Resources:
  Vol:
    Type: AWS::EC2::Volume
    Properties:
      AvailabilityZone: us-east-1a
      Size: 20
      Encrypted: false
"""
    findings = evaluate_first_resource(yaml_text, RULE)
    assert len(findings) == 1
    assert findings[0].severity is Severity.MEDIUM


def test_fail_encrypted_absent() -> None:
    """Encrypted absent → MEDIUM finding."""
    yaml_text = """\
Resources:
  Vol:
    Type: AWS::EC2::Volume
    Properties:
      AvailabilityZone: us-east-1a
      Size: 20
"""
    findings = evaluate_first_resource(yaml_text, RULE)
    assert len(findings) == 1


def test_no_finding_when_encrypted_is_intrinsic() -> None:
    """!Ref on Encrypted → no finding."""
    yaml_text = """\
Resources:
  Vol:
    Type: AWS::EC2::Volume
    Properties:
      AvailabilityZone: us-east-1a
      Size: 20
      Encrypted: !Ref EncryptedParam
"""
    assert evaluate_first_resource(yaml_text, RULE) == []
