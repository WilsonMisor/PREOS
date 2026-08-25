---
name: preos-architecture-economics
description: Evaluate architecture options as risk and economic hypotheses, reject premature complexity, define measurable activation triggers, and maintain ADR economics and Deferred Complexity Registry decisions.
---
# PREOS Architecture Economics

Run during Blueprint architecture and whenever workload, incidents, cost, threat, jurisdiction, vendor or team maturity materially changes assumptions.

1. Pair with `gstack-plan-eng-review`; PREOS does not replace engineering architecture review.
2. For every material option capture cost now, cost at next maturity stages, variable cost drivers, economic-abuse surface, complexity tax, operational/specialist burden, vendor concentration, failure cost, switching/migration cost and portability.
3. Prefer the simplest architecture that satisfies current proven requirements and nondeferrable production controls.
4. For deferred Redis, replicas, search clusters, Kafka, Kubernetes, service mesh, microservices, sharding, multi-region active-active, data lake/warehouse, graph database, CQRS, event sourcing, fraud platform, advanced observability, WAF/bot management, feature flag platform or other complexity, create a Deferred Complexity record with measurable activation trigger and migration path. `DEFERRED` without trigger is invalid.
5. Enrich Blueprint ADRs rather than creating conflicting architecture truth. Every major ADR gets economics, risk, migration path, activation assumptions, review trigger, accountable/implementation/reviewer/escalation roles and evidence.
6. Architecture is a hypothesis. Incidents, sustained workload changes, cost anomalies, new jurisdictions, threat-stage changes, vendor shifts and team maturity trigger review.
7. Output selected option, rejected options, economics, deferred-complexity IDs/triggers, ADR updates, risk/control implications and human decisions required.
