# Integrated Production Delivery Contract

PREOS is one component of a single operational delivery system. The repositories remain independently versioned, but they are not intended to operate as unrelated standalones when building production software.

## Responsibilities

| Layer | System | Responsibility |
|---|---|---|
| Human authority | Accountable people | Consequential decisions, risk acceptance, legal/compliance judgement, production approval |
| Lifecycle governance | AI Product Delivery Blueprint (`WilsonMisor/wed_dev_skill`) | Approved requirements, project classification, profiles, architecture baselines, task packets, traceability, gates, change control |
| Production assurance | PREOS (`WilsonMisor/PREOS`) | Risk, economics, control assessment, evidence validity, production gates, release risk, learning |
| Specialist workforce | gstack (`WilsonMisor/gstack`) | Product, architecture, design, security, code review, QA, benchmarking, release, deployment, canary, retrospective specialists |
| Implementation | Codex | Bounded implementation under approved AI Task Packets |
| Product surface | Application repository | Source code, project-specific artifacts, CI configuration, version-controlled governed state |

## Precedence

1. Human legal/organizational authority and explicit production approval cannot be overridden by AI.
2. Approved Blueprint baselines define what is being built.
3. PREOS can block or escalate production assurance but does not silently rewrite approved product requirements.
4. gstack findings are specialist evidence and recommendations, not independent approval authority.
5. Codex implements only approved bounded work and cannot broaden scope to satisfy speculative cleanup.

## Integration, not repository fusion

The systems integrate through named skills, artifacts, IDs, hashes, evidence, routing and project state. Do not copy the full Blueprint or gstack repository into PREOS. Do not copy PREOS into gstack. Do not use repository fusion as a substitute for a defined contract.
