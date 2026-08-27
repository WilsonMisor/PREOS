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

Resumable runtime state belongs under `PREOS_STATE_ROOT` and includes `PIPELINE-STATE.json`, `CURRENT-STATE.json`, `implementation-ledger.jsonl`, `approval-state.json`, `evidence-index.json`, `recovery-events.jsonl`, and `checkpoints/`.

## Canonical runtime state machine

PREOS uses these exact pipeline states:

```text
UNINITIALIZED
INGESTING
INTAKE_BLOCKED
PLANNING
PLAN_BLOCKED
PLAN_APPROVAL_REQUIRED
APPROVED_FOR_IMPLEMENTATION
IMPLEMENTING
IMPLEMENTATION_BLOCKED
VERIFYING
VERIFICATION_BLOCKED
APPROVED_FOR_RELEASE
RELEASE_BLOCKED
RELEASED
OPERATING
NEEDS_RECONCILIATION
RECOVERY_CONFLICT
```

`scripts/state_machine.py` is the executable transition contract. New schema-v1.2 checkpoints cannot write an arbitrary state or skip a prohibited transition. Implementation-free governed tasks may move from `PLANNING` directly to `VERIFYING`; code-changing tasks are expected to pass through `APPROVED_FOR_IMPLEMENTATION` and `IMPLEMENTING`.

Canonical ledger events include `TASK_ACCEPTED`, `TASK_PACKET_ISSUED`, `IMPLEMENTATION_STARTED`, `MEANINGFUL_EDIT_COMPLETE`, `TEST_BATCH_COMPLETE`, `BUILD_COMPLETE`, migration preparation/attempt/verification, `APPROVAL_REQUIRED`, `APPROVAL_RECEIVED`, `SESSION_INTERRUPTED`, `IMPLEMENTATION_COMPLETE`, `RELEASE_AUTHORISATION_REQUIRED`, and `RELEASED`. Recovery/checkpoint events are also explicit PREOS events. Unknown event types are recovery-integrity failures rather than ignorable notes.

## State classes and precedence

1. **Version-controlled governance truth** — approved Blueprint sources, Project Contract, task packets, approvals and PREOS project evidence.
2. **PREOS runtime/recovery state** — pipeline state, execution pointer, ledger, checkpoints, pending approvals and evidence index.
3. **External factual truth** — Git, CI, deployed environments, databases, monitoring, logs, billing systems and vendor consoles.
4. **gstack semantic context** — useful working-session notes only; not production-resume authority.

Conversation memory is never authoritative execution state.

## Reconciliation invariant

`PIPELINE-STATE.json`, the newest schema-valid checkpoint/`CURRENT-STATE.json`, and the append-only ledger are three persisted views of one governed execution. Recovery validates and reconciles all three; it does not silently choose one when they contradict each other. The runtime is also reconciled against Git branch/HEAD/working-tree fingerprint, Project Contract/source hashes, Task Packet, approvals, evidence freshness and any uncertain migration/test/build state.

For schema-v1.2 runtime state:

- missing or invalid `PIPELINE-STATE.json` is a recovery conflict;
- a pipeline/checkpoint task-packet, checkpoint, action or pending-state mismatch is a recovery conflict;
- an invalid JSON/JSONL/schema record is a recovery conflict;
- an unknown ledger event, duplicate event ID, backward timestamp, invalid checkpoint reference, or invalid state transition is a recovery conflict.

## Checkpoint invariant

Soft checkpoints preserve recoverable progress without claiming a verified boundary. Hard checkpoints require a clean coherent boundary, no uncertain test/build/migration/evidence state, and a last verified action. When the current AI Task Packet declares required checks or evidence, a hard checkpoint additionally requires a schema-valid verification manifest whose checks pass or are explicitly not applicable, whose evidence IDs are indexed and current, whose traceability status is recorded, and whose rollback point is explicit. PREOS does not accept a caller's prose claim as a substitute for declared proof.

Use event-based checkpoints and atomic JSON writes for continuity. After AI-session/context/terminal/network/PC interruption, run deterministic reconciliation before implementation continues. Resume only from the first unverified action after `SAFE_TO_RESUME`; keep pending approvals `BLOCKED`; use `RECOVERY_CONFLICT` when persisted state and reality disagree.

Read `docs/session-continuity.md` for the executable continuity/recovery contract.
