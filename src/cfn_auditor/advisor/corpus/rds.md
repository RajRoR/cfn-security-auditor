---
rule_ids: [CFN_RDS_001, CFN_RDS_002]
keywords: [rds, database, dbinstance, encryption, storageencrypted, public, accessible, kms]
---

# RDS DB Instance Hardening (CIS 2.3; Well-Architected SEC-08)

Production RDS instances must encrypt storage at rest and stay private.

- Set `StorageEncrypted: true`. Supply `KmsKeyId` for a customer-managed
  KMS key when the workload requires control over key rotation, sharing, or
  cross-account access.
- Set `PubliclyAccessible: false`. Place the instance in a private subnet
  and reach it via a bastion, VPC peering, or AWS PrivateLink. The default
  `false` is what you want — only override after a security review.
- Use `AWS::RDS::DBSubnetGroup` to pin the instance to private subnets.
- Pair encryption with `BackupRetentionPeriod` and `DeletionProtection: true`
  so the encryption posture survives operational mistakes.
