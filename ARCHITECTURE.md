# PREOS Architecture

## System position

```text
Human authority
      |
AI Product Delivery Blueprint
      |
      +-------------------+
      |                   |
    PREOS               gstack
production assurance   specialists
      |                   |
      +---------+---------+
                |
              Codex
                |
       Application repository
                |
       Staging / Production
                |
 incidents / telemetry / cost
                |
          PREOS learning
                |
       Blueprint change control
```

The systems are integrated but do not collapse into one source of truth. The Blueprint owns approved product truth and lifecycle gates. PREOS compiles that truth into a hash-bound Project Contract and assurance state. gstack performs specialist challenge and verification. Codex implements approved work. Humans approve consequential decisions.

## Lifecycle

1. Blueprint discovery and product definition, with `gstack-office-hours` and `gstack-plan-ceo-review` when applicable.
2. Approved PRD and Project Classification.
3. `$preos-project-init` creates the Project Contract, hashes, maturity/threat stage, role/authority map, vendor list, assumptions and UNKNOWNs.
4. `$preos-risk-model` applies the 75-control baseline and contextual risk selection/generation.
5. Blueprint architecture plus `gstack-plan-eng-review` and `$preos-architecture-economics`.
6. Design and SRS/SRD baselines.
7. `$preos-production-plan` enriches Blueprint AI Task Packets with risk, control, evidence, monitoring, recovery and economic requirements.
8. Human approval.
9. `$preos-production-implement` orchestrates bounded Codex implementation.
10. gstack review, security, QA and benchmarks as triggered.
11. PREOS G0-G11 production assurance evaluation.
12. Human production approval.
13. gstack ship, deploy and canary where authorised.
14. `$preos-production-learn`, gstack retro and Blueprint controlled change.

## Three classes of state

### Version-controlled project truth

`.ai-product-delivery/` in the application repository contains project contract, task packets, PREOS risk/control assessments, ADR links, evidence indexes, approvals and sanitized incident-learning records.

### Resumable local/agent state

`PREOS_STATE_ROOT` contains execution checkpoints, current state, implementation ledger, approval state, evidence index and recovery events. It is not a replacement for project truth and must never be stored under `GSTACK_STATE_ROOT`.

### External production truth

Git commits, CI runs, deployed artifacts, database state, monitoring, logs, billing, provider dashboards and other external systems remain authoritative for their own facts.
