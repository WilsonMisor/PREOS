---
name: preos
description: Production Risk, Economics, and Evolution Operating System. Integrates with the AI Product Delivery Blueprint, namespaced gstack specialists, and Codex to model real-world production risk, economics, evidence freshness, control dependencies, release risk and post-production learning without replacing human authority.
---

# PREOS Router

PREOS is the production-assurance plane of the integrated delivery system. Do not use it standalone for substantial software delivery: consume Blueprint-approved project truth, route specialist challenge to gstack, and bind Codex to approved Blueprint AI Task Packets.

## Immutable baseline and source coverage

- The original **75 controls** are the deterministic minimum and exist exactly once in canonical machine-readable form.
- The source risk corpus contains **1,130** atomic risks across **52** domains.
- The readiness bank contains **1,300** questions and must be selectively routed, not blindly loaded.
- The original uploaded package is hash-preserved under `source-package/`.
- Context-generated risks extend the baseline; they never replace it.

## Gate semantics

PREOS gate states are **GREEN, AMBER, RED, HUMAN REVIEW, UNKNOWN**. **UNKNOWN never silently becomes GREEN.** A GREEN claim requires current evidence. RED blocks the affected release path until remediated. HUMAN REVIEW requires qualified human action. Risk acceptance is time-bounded and human-authorised.

## Router

| Lifecycle point | PREOS route | Integrated companion |
|---|---|---|
| After Blueprint Project Classification | `$preos-project-init` | Blueprint classification |
| Initial risk pass, architecture change, task risk delta, release risk | `$preos-risk-model` | `gstack-cso` / `gstack-plan-eng-review` as triggered |
| Architecture selection and deferred complexity | `$preos-architecture-economics` | `gstack-plan-eng-review` |
| Before substantial implementation | `$preos-production-plan` | Blueprint AI Task Packet |
| Approved implementation | `$preos-production-implement` | Codex, then gstack review/QA |
| Incident/release/telemetry/cost learning | `$preos-production-learn` | `gstack-retro`, Blueprint change control |

## Risk passes

1. **Pass A:** after PRD and Project Classification. Identify product, security, privacy, money, tenant and major architecture risks.
2. **Pass B:** after architecture. Add database, queue, API, cache, vendor, failure, compatibility and economic risks.
3. **Risk delta:** before every substantial AI Task Packet, select risks created or changed by that packet.
4. **Release pass:** aggregate unresolved risk across the release and evaluate G0-G11.
5. **Learning pass:** after incidents or material production findings, create new/updated risk rules, tests, monitors, runbooks and architecture review triggers.

## Project Contract rule

The PREOS Project Contract is a compiled hash-bound snapshot of approved Blueprint sources. It is not a competing PRD, SRS or SRD. When a bound source changes, run change impact and evidence freshness review before relying on prior assurance results.

## State rule

- Version-controlled project truth: `.ai-product-delivery/preos/` inside the application repository.
- Resumable execution state: `PREOS_STATE_ROOT/projects/<project-id>/production/`.
- Never place PREOS truth under `.gstack/` or PREOS runtime state under `GSTACK_STATE_ROOT`.
- External Git/CI/runtime/provider systems remain authoritative for facts they own.

## Selective loading

Never load all 1,130 risks or ask all 1,300 questions unless the task truly requires a complete catalogue audit. Select by Project Contract, active Blueprint profiles, feature, changed components, maturity stage, threat stage and current risk graph.

## AI Task Packet integration

The Blueprint AI Task Packet remains the canonical implementation unit. PREOS extends it with requirement IDs, risk IDs, control IDs, ADR/deferred-complexity IDs, failure tests, evidence, monitoring, recovery, reconciliation, economics, gstack routes and named human approver. Do not invent a competing implementation object.

## gstack integration

PREOS routes specialist work to namespaced gstack commands such as `gstack-office-hours`, `gstack-plan-ceo-review`, `gstack-plan-eng-review`, `gstack-plan-design-review`, `gstack-cso`, `gstack-review`, `gstack-investigate`, `gstack-qa`, `gstack-qa-only`, `gstack-benchmark`, `gstack-ship`, `gstack-land-and-deploy`, `gstack-canary` and `gstack-retro`. Provide requirement/risk/control/evidence IDs and current gate state. gstack cannot accept risk or silently rewrite approved Blueprint baselines.

## Production gates

Evaluate G0 through G11 from `references/gates/production-gates.json`. These broader gates sit over, and do not renumber or weaken, the original 75-control baseline.

## Human authority boundary

AI may analyze, propose, implement approved scope, test, measure, collect evidence, recommend and escalate. AI may not accept material risk; approve its own security/privacy/legal/financial exception; waive a failing gate; declare compliance; silently introduce paid vendors; mutate production data without authority; expand scope/architecture beyond approval; or execute irreversible production release without explicit delegated human authority. Missing qualified authority is a **ROLE GAP**, not an AI vacancy.

## Completion

Return active Blueprint source versions/hashes, PREOS stage, selected risk/control IDs, current UNKNOWN/HUMAN REVIEW/RED items, gstack routes invoked or required, Codex task packet status, evidence freshness, G0-G11 state, human approvals/role gaps, deferred-complexity triggers, limitations and next lifecycle route.
