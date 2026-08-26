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

Blueprint source-intake state may additionally exist under `.ai-product-delivery/source-intake/`; that intake state does not replace the PREOS Project Contract.

Resumable runtime state belongs under `PREOS_STATE_ROOT` and may include `PIPELINE-STATE.json`, `CURRENT-STATE.json`, `implementation-ledger.jsonl`, `approval-state.json`, `evidence-index.json`, `recovery-events.jsonl`, and `checkpoints/`.

## State classes and precedence

1. **Version-controlled governance truth** — approved Blueprint sources, Project Contract, task packets, approvals and PREOS project evidence.
2. **PREOS runtime/recovery state** — execution pointer, ledger, checkpoints, pending approvals and evidence index.
3. **External factual truth** — Git, CI, deployed environments, databases, monitoring, logs, billing systems and vendor consoles.
4. **gstack semantic context** — useful working-session notes only; not production-resume authority.

Conversation memory is never authoritative execution state.

Use event-based soft/hard checkpoints and atomic JSON writes for continuity. After AI-session/context/terminal/network/PC interruption, run deterministic reconciliation before implementation continues. Compare Project Contract/task/source bindings and PREOS runtime state against actual Git/external truth. Resume only from the first unverified action after `SAFE_TO_RESUME`; keep pending approvals `BLOCKED`; use `RECOVERY_CONFLICT` when state sources disagree.

Read `docs/session-continuity.md` for the executable continuity/recovery contract.
