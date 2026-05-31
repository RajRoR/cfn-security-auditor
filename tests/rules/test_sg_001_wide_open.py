"""CFN_SG_001 — SecurityGroup ingress from anywhere; CRITICAL on SSH/RDP."""

from cfn_auditor.rules import Severity
from cfn_auditor.rules.checks.sg import SecurityGroupWideOpenIngress
from tests.rules._helpers import evaluate_first_resource

RULE = SecurityGroupWideOpenIngress()


def test_pass_scoped_cidr() -> None:
    """Ingress from a scoped CIDR → no finding."""
    yaml_text = """\
Resources:
  Locked:
    Type: AWS::EC2::SecurityGroup
    Properties:
      GroupDescription: locked
      SecurityGroupIngress:
        - IpProtocol: tcp
          FromPort: 443
          ToPort: 443
          CidrIp: 10.0.0.0/16
"""
    assert evaluate_first_resource(yaml_text, RULE) == []


def test_fail_open_cidr_high_severity() -> None:
    """0.0.0.0/0 on a non-SSH/RDP port → HIGH."""
    yaml_text = """\
Resources:
  Open:
    Type: AWS::EC2::SecurityGroup
    Properties:
      GroupDescription: open
      SecurityGroupIngress:
        - IpProtocol: tcp
          FromPort: 443
          ToPort: 443
          CidrIp: 0.0.0.0/0
"""
    findings = evaluate_first_resource(yaml_text, RULE)
    assert len(findings) == 1
    assert findings[0].severity is Severity.HIGH


def test_fail_open_cidr_ssh_critical() -> None:
    """0.0.0.0/0 on port 22 → CRITICAL."""
    yaml_text = """\
Resources:
  SshOpen:
    Type: AWS::EC2::SecurityGroup
    Properties:
      GroupDescription: ssh
      SecurityGroupIngress:
        - IpProtocol: tcp
          FromPort: 22
          ToPort: 22
          CidrIp: 0.0.0.0/0
"""
    findings = evaluate_first_resource(yaml_text, RULE)
    assert len(findings) == 1
    assert findings[0].severity is Severity.CRITICAL


def test_fail_open_cidr_rdp_critical() -> None:
    """0.0.0.0/0 on port 3389 → CRITICAL."""
    yaml_text = """\
Resources:
  RdpOpen:
    Type: AWS::EC2::SecurityGroup
    Properties:
      GroupDescription: rdp
      SecurityGroupIngress:
        - IpProtocol: tcp
          FromPort: 3389
          ToPort: 3389
          CidrIp: 0.0.0.0/0
"""
    findings = evaluate_first_resource(yaml_text, RULE)
    assert findings[0].severity is Severity.CRITICAL


def test_fail_port_range_covering_ssh() -> None:
    """A range 0-1024 covering 22 → CRITICAL."""
    yaml_text = """\
Resources:
  RangeOpen:
    Type: AWS::EC2::SecurityGroup
    Properties:
      GroupDescription: range
      SecurityGroupIngress:
        - IpProtocol: tcp
          FromPort: 0
          ToPort: 1024
          CidrIp: 0.0.0.0/0
"""
    findings = evaluate_first_resource(yaml_text, RULE)
    assert findings[0].severity is Severity.CRITICAL


def test_fail_all_ports_sentinel_critical() -> None:
    """FromPort -1 (all ports) covers SSH/RDP → CRITICAL."""
    yaml_text = """\
Resources:
  All:
    Type: AWS::EC2::SecurityGroup
    Properties:
      GroupDescription: all
      SecurityGroupIngress:
        - IpProtocol: '-1'
          FromPort: -1
          ToPort: -1
          CidrIp: 0.0.0.0/0
"""
    findings = evaluate_first_resource(yaml_text, RULE)
    assert findings[0].severity is Severity.CRITICAL


def test_fail_open_ipv6() -> None:
    """::/0 on CidrIpv6 → finding."""
    yaml_text = """\
Resources:
  V6:
    Type: AWS::EC2::SecurityGroup
    Properties:
      GroupDescription: v6
      SecurityGroupIngress:
        - IpProtocol: tcp
          FromPort: 443
          ToPort: 443
          CidrIpv6: ::/0
"""
    findings = evaluate_first_resource(yaml_text, RULE)
    assert len(findings) == 1


def test_no_finding_when_cidr_is_intrinsic() -> None:
    """!Ref on CidrIp → no finding."""
    yaml_text = """\
Resources:
  Refd:
    Type: AWS::EC2::SecurityGroup
    Properties:
      GroupDescription: refd
      SecurityGroupIngress:
        - IpProtocol: tcp
          FromPort: 443
          ToPort: 443
          CidrIp: !Ref AllowedCidr
"""
    assert evaluate_first_resource(yaml_text, RULE) == []


def test_no_finding_when_port_is_intrinsic_does_not_escalate() -> None:
    """Open CIDR with intrinsic ports → HIGH (no escalation), still fires."""
    yaml_text = """\
Resources:
  PortRefd:
    Type: AWS::EC2::SecurityGroup
    Properties:
      GroupDescription: portrefd
      SecurityGroupIngress:
        - IpProtocol: tcp
          FromPort: !Ref FromPortParam
          ToPort: !Ref ToPortParam
          CidrIp: 0.0.0.0/0
"""
    findings = evaluate_first_resource(yaml_text, RULE)
    assert len(findings) == 1
    assert findings[0].severity is Severity.HIGH


def test_no_ingress_property_no_finding() -> None:
    """SG with no SecurityGroupIngress at all → no finding."""
    yaml_text = """\
Resources:
  Empty:
    Type: AWS::EC2::SecurityGroup
    Properties:
      GroupDescription: empty
"""
    assert evaluate_first_resource(yaml_text, RULE) == []


def test_no_finding_when_ingress_value_is_intrinsic() -> None:
    """!Ref on the entire SecurityGroupIngress list → no finding."""
    yaml_text = """\
Resources:
  Refd:
    Type: AWS::EC2::SecurityGroup
    Properties:
      GroupDescription: refd
      SecurityGroupIngress: !Ref IngressParam
"""
    assert evaluate_first_resource(yaml_text, RULE) == []
