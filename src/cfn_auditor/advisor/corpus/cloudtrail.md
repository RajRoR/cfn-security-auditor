---
rule_ids: [CFN_CT_001]
keywords: [cloudtrail, trail, kms, kmskeyid, encryption, logging]
---

# CloudTrail Log Encryption (CIS 3.x)

CloudTrail log files capture every API call in the account; their
confidentiality and integrity matter.

- Set `KMSKeyId` on every `AWS::CloudTrail::Trail` to encrypt log files with
  a customer-managed KMS key (CMK). The CMK key policy should grant
  `kms:Decrypt` only to operators that legitimately need access to the trail
  data.
- Enable `IncludeGlobalServiceEvents: true` and `IsMultiRegionTrail: true`
  for org-wide visibility.
- Enable log-file integrity validation (`EnableLogFileValidation: true`) so
  tampering is detectable even if the bucket policy is subverted.
- Pair the trail with an `AWS::S3::Bucket` whose `BucketEncryption` and
  `PublicAccessBlockConfiguration` are tightened (see the S3 guidance).
