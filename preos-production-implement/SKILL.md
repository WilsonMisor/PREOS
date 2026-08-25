---
name: preos-production-implement
description: Orchestrate Codex implementation of an approved PREOS-enriched Blueprint AI Task Packet, collect evidence, and route independent gstack review/QA without expanding scope or self-approving production risk.
---
# PREOS Production Implement

1. Require an approved Blueprint AI Task Packet enriched by PREOS. Do not implement unresolved scope, authority or hard prerequisite conflicts.
2. Codex implements the smallest coherent approved change in the application repository. Preserve existing naming, schema, API, environment and architecture conventions unless the packet explicitly changes them.
3. Add required tests, observability, failure handling, recovery/reconciliation and evidence generation with the code.
4. Do not silently add packages, tables, services, paid vendors, permissions, environment variables or architecture layers.
5. Run the packet's automated checks and record evidence with commit/config/environment binding.
6. Route independent review to `gstack-review`; route threat/security findings to `gstack-cso`; use `gstack-qa` or `gstack-qa-only` for browser QA; `gstack-benchmark` for performance/capacity evidence; `gstack-investigate` for root-cause work.
7. Re-run affected PREOS controls/risks after implementation. Old evidence becomes STALE when bound inputs changed.
8. Before release, evaluate G0-G11. AI cannot turn UNKNOWN, HUMAN REVIEW or RED into GREEN without required evidence/human decision.
9. Human production approval is separate from code completion and separate from merge approval.
10. After human approval, gstack ship/deploy/canary may run if explicitly authorised. Return implementation evidence, review findings, gate state and unresolved items.
