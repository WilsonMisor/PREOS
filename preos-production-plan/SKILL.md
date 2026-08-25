---
name: preos-production-plan
description: Convert approved Blueprint scope plus PREOS risk/control/economic requirements into enriched bounded AI Task Packets with tests, evidence, monitoring, recovery, reconciliation, reviewer routes and human authority.
---
# PREOS Production Plan

The Blueprint AI Task Packet is the only canonical implementation unit. PREOS extends it; do not create a competing plan object.

1. Confirm source hashes and architecture are current. If upstream truth changed, run change impact before planning.
2. Attach requirement IDs, selected risk IDs, applicable 75-control IDs, ADRs and deferred-complexity IDs.
3. Define allowed files/systems/environments and prohibited actions.
4. Define applicable positive, negative, duplicate/retry, concurrency, permission/cross-tenant, provider-failure, stale-state, migration/rollback, restore, reconciliation, invariant, load, capacity and cost tests.
5. Define evidence records including commit/config/environment bindings, freshness/invalidation rules and artifact locations.
6. Define monitoring, alerting, recovery, reconciliation and operational handoff expectations.
7. Identify gstack specialist routes: review, cso, qa/qa-only, benchmark, design or engineering review as applicable.
8. Name human reviewer/approver and production authority. ROLE GAP blocks consequential approval.
9. Require explicit human approval before `$preos-production-implement` for consequential or launch-scope work.
10. Output the enriched packet, risk delta, expected G0-G11 impact, evidence plan, specialist routes and approval state.
