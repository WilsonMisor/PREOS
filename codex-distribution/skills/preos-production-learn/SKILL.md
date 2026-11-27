---
name: preos-production-learn
description: Convert incidents, telemetry, support findings, cost anomalies, security events and release outcomes into new risk rules, regression tests, monitors, runbooks, stale-evidence invalidation and Blueprint controlled-change proposals.
---
# PREOS Production Learn

Run after incidents, material near-misses, significant support patterns, cost anomalies, security findings, releases, rollback events, restore tests or architecture-trigger events.

1. Capture incident/observation ID, impact, root cause, trigger and contributing technical, human and economic factors.
2. Determine why the existing risk/control system failed to prevent or detect it.
3. Create or update risk rules, baseline applicability notes without renumbering the 75 controls, regression tests, monitoring, alerts, runbooks, reconciliation and recovery procedures.
4. Invalidate stale evidence and flag ADR/deferred-complexity assumptions whose triggers were met or invalidated.
5. Update risk aggregation and future release review triggers.
6. Use `gstack-investigate` for unresolved root cause and `gstack-retro` for retrospective learning.
7. Route product/architecture requirement changes through Blueprint change control. PREOS must not silently rewrite approved PRD/SRS/SRD/architecture.
8. Record human owners and approvals for risk acceptance or consequential operational policy changes.
9. Output incident-learning record, new/changed risk/test/monitor/runbook IDs, stale evidence, architecture review triggers and Blueprint change requests.
