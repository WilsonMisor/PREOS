---
name: preos-project-init
description: Compile Blueprint-approved project truth into a hash-bound PREOS Project Contract, production-assurance activation, maturity/threat stage, authority map, vendor inventory, assumptions, unknowns and state roots.
---
# PREOS Project Init

Run only after the AI Product Delivery Blueprint has an approved PRD and Project Classification sufficient to identify authoritative sources.

1. Inventory approved PRD, SRS, SRD, Project Classification, architecture/design baselines, ADRs, threat/privacy records, environment constraints and relevant contracts.
2. Hash every authoritative source. Conflicts are blocking UNKNOWNs; never choose a winner silently.
3. Record active Blueprint profiles and PREOS assurance level: inactive, lightweight, standard, or high-assurance.
4. Record maturity stage 0-5, threat stage, financial consequence, personal/sensitive data, multi-tenancy, money movement, critical operations, vendor reliance and regulatory/accessibility triggers.
5. Record accountable human roles for product scope, architecture, security risk, privacy, legal, finance/custody, production launch, emergency shutdown, risk acceptance, destructive data operations, paid vendors and compliance. Missing qualified authority is ROLE GAP.
6. Create/update `.ai-product-delivery/project-contract/` and `.ai-product-delivery/preos/` using `../preos/scripts/init-project-state.py`. Runtime checkpoints go to PREOS_STATE_ROOT, never GSTACK_STATE_ROOT.
7. The Project Contract is compiled truth, not a replacement PRD/SRS/SRD. Source hash drift triggers change-impact and evidence-freshness review.
8. Output Project Contract ID/version/hash set, assurance level, stages, role gaps, vendors, assumptions, UNKNOWNs and next route `$preos-risk-model`.
