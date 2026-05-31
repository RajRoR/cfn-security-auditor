---
rule_ids: [CFN_SG_001]
keywords: [securitygroup, ingress, cidr, port, ssh, rdp, network]
---

# EC2 Security Group Ingress (CIS 4.x)

Security-group ingress should be the smallest allow-list required.

- Ingress with `CidrIp 0.0.0.0/0` or `CidrIpv6 ::/0` exposes the listening
  port to the entire internet. For SSH (TCP/22) and RDP (TCP/3389) this is
  a CIS-flagged finding regardless of context.
- Replace open CIDRs with the smallest network range that satisfies the
  workload (corp VPN range, an ALB security group via
  `SourceSecurityGroupId`, or a known partner CIDR).
- Constrain `FromPort`/`ToPort` to the exact ports the service listens on;
  avoid `-1` (all ports) outside emergency administrative SGs.
- Stand up a bastion or AWS Systems Manager Session Manager rather than
  exposing 22/3389 to the internet.
