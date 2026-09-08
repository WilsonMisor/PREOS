# PREOS Production Gates

Gate states are **GREEN, AMBER, RED, HUMAN REVIEW, UNKNOWN**. UNKNOWN never silently becomes GREEN.

## G0 Source / Project Contract

Authoritative sources inventoried and hashed; conflicts resolved; assumptions explicit; scope, stack, maturity, threat stage, roles and authority current.

## G1 Product / Business Correctness

Business invariants, invalid states, pricing, entitlements, manual workflows and acceptance criteria are explicit and tested.

## G2 Architecture

Architecture matches actual need, dependencies and failure policies are explicit, premature complexity is rejected, migration and review triggers exist.

## G3 Security / Identity / Trust / Privacy

Authentication, authorization, tenant isolation, abuse, secrets, supply chain, privacy and trust controls pass applicable tests; professional review recorded where required.

## G4 Data Correctness

Semantics, integrity, concurrency, migration, lineage, quality, retention and silent-wrongness controls are proven.

## G5 Financial Correctness / Economics

Money, reconciliation, billing and custody controls are proven where applicable; unit economics and economic-abuse exposure are acceptable.

## G6 Performance / Capacity

Measured workloads fit resources; hotspots, tenant concentration, quotas, retry amplification and cost scaling have acceptable headroom or planned triggers.

## G7 Failure / Recovery

Timeouts, retries, degradation, backpressure, failover, backups, restores, rollback or forward repair and reconciliation are tested.

## G8 Change / Deployment Safety

Change impact, compatibility, migration ordering, artifact provenance, environment drift, canary, rollback and production promotion are controlled.

## G9 Operations / Support

Monitoring, ownership, support and admin tools, escalation, runbooks, incident command, toil and human-error controls are ready.

## G10 Legal / Compliance / Accessibility

Applicable requirements are identified, current research performed where necessary, evidence retained, and qualified human decisions recorded.

## G11 Evidence / Authority

Every GREEN claim has current evidence bound to code, configuration and environment; HUMAN REVIEW approvals are explicit; accepted risks expire and have review triggers.
