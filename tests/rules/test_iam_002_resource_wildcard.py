"""CFN_IAM_002 — IAM Allow statement with Resource '*'."""

from cfn_auditor.rules import Severity
from cfn_auditor.rules.checks.iam import IamAllowResourceWildcard
from tests.rules._helpers import evaluate_first_resource

RULE = IamAllowResourceWildcard()


def test_pass_scoped_resource() -> None:
    """Allow with a specific Resource ARN → no finding."""
    yaml_text = """\
Resources:
  Pol:
    Type: AWS::IAM::Policy
    Properties:
      PolicyName: scoped
      PolicyDocument:
        Statement:
          - Effect: Allow
            Action: s3:GetObject
            Resource: arn:aws:s3:::bucket/*
"""
    assert evaluate_first_resource(yaml_text, RULE) == []


def test_fail_resource_star() -> None:
    """Resource '*' on Allow → MEDIUM finding."""
    yaml_text = """\
Resources:
  Pol:
    Type: AWS::IAM::Policy
    Properties:
      PolicyName: open
      PolicyDocument:
        Statement:
          - Effect: Allow
            Action: s3:GetObject
            Resource: '*'
"""
    findings = evaluate_first_resource(yaml_text, RULE)
    assert len(findings) == 1
    assert findings[0].severity is Severity.MEDIUM


def test_fail_resource_star_in_list() -> None:
    """Resource list containing '*' → finding."""
    yaml_text = """\
Resources:
  Pol:
    Type: AWS::IAM::Policy
    Properties:
      PolicyName: mixed
      PolicyDocument:
        Statement:
          - Effect: Allow
            Action: s3:GetObject
            Resource: ['arn:aws:s3:::bucket/*', '*']
"""
    findings = evaluate_first_resource(yaml_text, RULE)
    assert len(findings) == 1


def test_intrinsic_resource_skipped() -> None:
    """Allow with intrinsic Resource → no finding."""
    yaml_text = """\
Resources:
  Pol:
    Type: AWS::IAM::Policy
    Properties:
      PolicyName: refd
      PolicyDocument:
        Statement:
          - Effect: Allow
            Action: s3:GetObject
            Resource: !Ref ResourceParam
"""
    assert evaluate_first_resource(yaml_text, RULE) == []
