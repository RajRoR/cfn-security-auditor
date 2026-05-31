---
rule_ids: [CFN_EC2_001]
keywords: [ec2, ebs, volume, encrypted, kms, encryption]
---

# EC2 EBS Volume Encryption (CIS 2.x)

EBS volumes carry workload data and must be encrypted at rest.

- Set `Encrypted: true` on every `AWS::EC2::Volume`. Supply `KmsKeyId` for
  a customer-managed KMS key when needed; otherwise the AWS-managed default
  EBS key is acceptable for general workloads.
- Enable account-level "EBS encryption by default"
  (`aws ec2 enable-ebs-encryption-by-default`) so newly created volumes get
  encryption regardless of template oversight.
- For block-device-mapping inside `AWS::EC2::Instance` and
  `AWS::AutoScaling::LaunchConfiguration`, the same `Encrypted: true` rule
  applies to every BDM entry.
