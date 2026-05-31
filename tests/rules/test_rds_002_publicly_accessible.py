"""CFN_RDS_002 — RDS DB instance with PubliclyAccessible true."""

from cfn_auditor.rules import Severity
from cfn_auditor.rules.checks.rds import RdsPubliclyAccessible
from tests.rules._helpers import evaluate_first_resource

RULE = RdsPubliclyAccessible()


def test_pass_public_false() -> None:
    """PubliclyAccessible literally false → no finding."""
    yaml_text = """\
Resources:
  Db:
    Type: AWS::RDS::DBInstance
    Properties:
      DBInstanceClass: db.t3.micro
      Engine: mysql
      PubliclyAccessible: false
"""
    assert evaluate_first_resource(yaml_text, RULE) == []


def test_pass_property_absent() -> None:
    """PubliclyAccessible absent → no finding (AWS default is private)."""
    yaml_text = """\
Resources:
  Db:
    Type: AWS::RDS::DBInstance
    Properties:
      DBInstanceClass: db.t3.micro
      Engine: mysql
"""
    assert evaluate_first_resource(yaml_text, RULE) == []


def test_fail_public_true() -> None:
    """PubliclyAccessible literally true → CRITICAL finding."""
    yaml_text = """\
Resources:
  Db:
    Type: AWS::RDS::DBInstance
    Properties:
      DBInstanceClass: db.t3.micro
      Engine: mysql
      PubliclyAccessible: true
"""
    findings = evaluate_first_resource(yaml_text, RULE)
    assert len(findings) == 1
    assert findings[0].severity is Severity.CRITICAL


def test_no_finding_when_public_is_intrinsic() -> None:
    """!Ref on PubliclyAccessible → no finding."""
    yaml_text = """\
Resources:
  Db:
    Type: AWS::RDS::DBInstance
    Properties:
      DBInstanceClass: db.t3.micro
      Engine: mysql
      PubliclyAccessible: !Ref PublicParam
"""
    assert evaluate_first_resource(yaml_text, RULE) == []
