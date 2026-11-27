---
name: preos-production-implement
description: Orchestrate Codex implementation of an approved PREOS-enriched Blueprint AI Task Packet, collect evidence, maintain recoverable execution state, and route independent gstack review/QA without expanding scope or self-approving production risk.
---
# PREOS Production Implement

1. Require an approved Blueprint AI Task Packet enriched by PREOS. Do not implement unresolved scope, authority or hard prerequisite conflicts.
2. Before editing, if prior production-relevant implementation may have been interrupted, run PREOS deterministic recovery. Conversation memory or gstack context alone is not authority to resume. Continue only after `SAFE_TO_RESUME`; preserve `BLOCKED`; stop on `RECOVERY_CONFLICT`.
3. Codex implements the smallest coherent approved change in the application repository. Preserve existing naming, schema, API, environment and architecture conventions unless the packet explicitly changes them.
4. Add required tests, observability, failure handling, recovery/reconciliation and evidence generation with the code.
5. Do not silently add packages, tables, services, paid vendors, permissions, environment variables or architecture layers.
6. Use event-based PREOS checkpoints at meaningful implementation/test/migration/approval boundaries. Soft checkpoints persist runtime state without a Git commit. Hard checkpoints require a coherent verified boundary and record Git state; PREOS never auto-commits or pushes simply to create a checkpoint.
7. Persist consequential approval state. Pending human approval remains pending across AI-session loss and must not be inferred from prior chat tone.
8. Run the packet's automated checks and record evidence with commit/config/environment binding. Resume after interruption from the first unverified action rather than the last conversational topic.
9. Route independent review to `gstack-review`; route threat/security findings to `gstack-cso`; use `gstack-qa` or `gstack-qa-only` for browser QA; `gstack-benchmark` for performance/capacity evidence; `gstack-investigate` for root-cause work.
10. Re-run affected PREOS controls/risks after implementation. Old evidence becomes STALE when bound inputs changed.
11. Before release, evaluate G0-G11. AI cannot turn UNKNOWN, HUMAN REVIEW or RED into GREEN without required evidence/human decision.
12. Human production approval is separate from code completion and separate from merge approval.
13. After human approval, gstack ship/deploy/canary may run if explicitly authorised. Return implementation evidence, review findings, recovery/checkpoint state, gate state and unresolved items.
