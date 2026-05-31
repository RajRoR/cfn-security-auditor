---
rule_ids: [CFN_IAM_001, CFN_IAM_002]
keywords: [iam, policy, action, resource, allow, wildcard, statement]
---

# IAM Policy Wildcards (CIS 1.x; Well-Architected SEC-03)

IAM policies must scope `Action` and `Resource` as narrowly as the workload
allows.

- `Effect: Allow` combined with `Action: "*"` confers full administrative
  access to whatever principal carries the policy. Replace with the explicit
  set of API actions the principal needs (e.g. `s3:GetObject`,
  `s3:PutObject`).
- `Effect: Allow` combined with `Resource: "*"` makes that allow apply to
  every resource of every service the action covers. Replace with explicit
  ARNs (e.g. `arn:aws:s3:::my-bucket/*`).
- Service-scoped wildcards (`s3:*`) are sometimes acceptable on
  development-only roles but should still be tightened for production
  workloads. Audit them via `aws iam simulate-principal-policy`.
- Pair every Allow statement with a `Condition` block where feasible — the
  bar for production is "least privilege plus context."
