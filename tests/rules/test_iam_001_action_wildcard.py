"""CFN_IAM_001 — IAM Allow statement with Action '*'."""

from cfn_auditor.rules import Severity
from cfn_auditor.rules.checks.iam import IamAllowActionWildcard
from tests.rules._helpers import evaluate_first_resource

RULE = IamAllowActionWildcard()


def test_pass_scoped_action() -> None:
    """Allow with a specific action → no finding."""
    yaml_text = """\
Resources:
  Pol:
    Type: AWS::IAM::Policy
    Properties:
      PolicyName: scoped
      PolicyDocument:
        Version: "2012-10-17"
        Statement:
          - Effect: Allow
            Action: s3:GetObject
            Resource: arn:aws:s3:::bucket/*
"""
    assert evaluate_first_resource(yaml_text, RULE) == []


def test_pass_service_scoped_wildcard_not_flagged() -> None:
    """s3:* is service-scoped — MVP does not flag it."""
    yaml_text = """\
Resources:
  Pol:
    Type: AWS::IAM::Policy
    Properties:
      PolicyName: scoped
      PolicyDocument:
        Version: "2012-10-17"
        Statement:
          - Effect: Allow
            Action: s3:*
            Resource: '*'
"""
    assert evaluate_first_resource(yaml_text, RULE) == []


def test_fail_action_star_string() -> None:
    """Action '*' as a string → HIGH finding."""
    yaml_text = """\
Resources:
  Pol:
    Type: AWS::IAM::Policy
    Properties:
      PolicyName: open
      PolicyDocument:
        Version: "2012-10-17"
        Statement:
          - Effect: Allow
            Action: '*'
            Resource: '*'
"""
    findings = evaluate_first_resource(yaml_text, RULE)
    assert len(findings) == 1
    assert findings[0].severity is Severity.HIGH


def test_fail_action_star_in_list() -> None:
    """Action ['s3:GetObject', '*'] → finding."""
    yaml_text = """\
Resources:
  Pol:
    Type: AWS::IAM::Policy
    Properties:
      PolicyName: mixed
      PolicyDocument:
        Statement:
          - Effect: Allow
            Action: [s3:GetObject, '*']
            Resource: '*'
"""
    findings = evaluate_first_resource(yaml_text, RULE)
    assert len(findings) == 1


def test_pass_deny_with_action_star() -> None:
    """Effect Deny with Action '*' → no finding (only Allow fires)."""
    yaml_text = """\
Resources:
  Pol:
    Type: AWS::IAM::Policy
    Properties:
      PolicyName: deny
      PolicyDocument:
        Statement:
          - Effect: Deny
            Action: '*'
            Resource: '*'
"""
    assert evaluate_first_resource(yaml_text, RULE) == []


def test_role_inline_policies_evaluated() -> None:
    """Role with inline Policies list → rule walks each policy."""
    yaml_text = """\
Resources:
  Role:
    Type: AWS::IAM::Role
    Properties:
      AssumeRolePolicyDocument:
        Statement:
          - Effect: Allow
            Principal: {Service: lambda.amazonaws.com}
            Action: sts:AssumeRole
      Policies:
        - PolicyName: inline
          PolicyDocument:
            Statement:
              - Effect: Allow
                Action: '*'
                Resource: '*'
"""
    findings = evaluate_first_resource(yaml_text, RULE)
    assert len(findings) == 1


def test_statement_as_single_dict_normalised() -> None:
    """Statement is a single dict (not a list) → still evaluated."""
    yaml_text = """\
Resources:
  Pol:
    Type: AWS::IAM::ManagedPolicy
    Properties:
      ManagedPolicyName: solo
      PolicyDocument:
        Statement:
          Effect: Allow
          Action: '*'
          Resource: '*'
"""
    findings = evaluate_first_resource(yaml_text, RULE)
    assert len(findings) == 1


def test_intrinsic_policy_document_skipped() -> None:
    """An intrinsic PolicyDocument is dropped — no finding, no crash."""
    yaml_text = """\
Resources:
  Pol:
    Type: AWS::IAM::Policy
    Properties:
      PolicyName: refd
      PolicyDocument: !Ref PolicyDocParam
"""
    assert evaluate_first_resource(yaml_text, RULE) == []


def test_intrinsic_action_skipped() -> None:
    """Allow with intrinsic Action → no finding."""
    yaml_text = """\
Resources:
  Pol:
    Type: AWS::IAM::Policy
    Properties:
      PolicyName: refdaction
      PolicyDocument:
        Statement:
          - Effect: Allow
            Action: !Ref ActionParam
            Resource: 'arn:aws:s3:::bucket/*'
"""
    assert evaluate_first_resource(yaml_text, RULE) == []
