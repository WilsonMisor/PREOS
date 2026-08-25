# Application Project State

PREOS project-specific version-controlled state belongs in the application repository, not inside the PREOS repository and not under `.gstack/`.

```text
.ai-product-delivery/
  project-contract/
  task-packets/
  approvals/
  preos/
    risk-model/
    control-assessments/
    architecture-economics/
    deferred-complexity/
    gate-state/
    evidence/
    risk-acceptance/
    incidents/
    traceability/
```

Resumable runtime state belongs under `PREOS_STATE_ROOT` and may include `PIPELINE-STATE.json`, `CURRENT-STATE.json`, `implementation-ledger.jsonl`, `approval-state.json`, `evidence-index.json`, `recovery-events.jsonl`, and checkpoints.

External runtime facts remain authoritative in Git, CI, deployed environments, databases, monitoring, logs, billing systems and vendor consoles.
