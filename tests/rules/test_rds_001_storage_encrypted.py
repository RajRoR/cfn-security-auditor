"""CFN_RDS_001 — RDS DB instance with StorageEncrypted false or absent."""

from cfn_auditor.rules import Severity
from cfn_auditor.rules.checks.rds import RdsStorageNotEncrypted
from tests.rules._helpers import evaluate_first_resource

RULE = RdsStorageNotEncrypted()


def test_pass_encrypted_true() -> None:
    """StorageEncrypted literally true → no finding."""
    yaml_text = """\
Resources:
  Db:
    Type: AWS::RDS::DBInstance
    Properties:
      DBInstanceClass: db.t3.micro
      Engine: mysql
      AllocatedStorage: '20'
      MasterUsername: admin
      StorageEncrypted: true
"""
    assert evaluate_first_resource(yaml_text, RULE) == []


def test_fail_encrypted_false() -> None:
    """StorageEncrypted literally false → HIGH finding."""
    yaml_text = """\
Resources:
  Db:
    Type: AWS::RDS::DBInstance
    Properties:
      DBInstanceClass: db.t3.micro
      Engine: mysql
      StorageEncrypted: false
"""
    findings = evaluate_first_resource(yaml_text, RULE)
    assert len(findings) == 1
    assert findings[0].severity is Severity.HIGH


def test_fail_encrypted_absent() -> None:
    """StorageEncrypted absent → HIGH finding."""
    yaml_text = """\
Resources:
  Db:
    Type: AWS::RDS::DBInstance
    Properties:
      DBInstanceClass: db.t3.micro
      Engine: mysql
"""
    findings = evaluate_first_resource(yaml_text, RULE)
    assert len(findings) == 1


def test_no_finding_when_encrypted_is_intrinsic() -> None:
    """!Ref on StorageEncrypted → no finding."""
    yaml_text = """\
Resources:
  Db:
    Type: AWS::RDS::DBInstance
    Properties:
      DBInstanceClass: db.t3.micro
      Engine: mysql
      StorageEncrypted: !Ref EncryptionParam
"""
    assert evaluate_first_resource(yaml_text, RULE) == []
