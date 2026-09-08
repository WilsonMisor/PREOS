# AI Session Continuity, Checkpoints, and Recovery

PREOS treats loss of the AI coding session as a production-process failure mode. The development system must remain recoverable after Codex context loss, process/terminal/network interruption, deliberate stop, or PC restart.

## Doctrine

Conversation memory is never authoritative execution state.

The continuity model has four layers:

1. Blueprint/application governance under `.ai-product-delivery/` establishes approved source authority, requirements, architecture, task packets and approvals.
2. PREOS runtime state under `PREOS_STATE_ROOT` establishes the pipeline state, last verified execution state, checkpoints, ledger, approvals and evidence index.
3. Git, CI, deployed environments, databases, monitoring, logs and vendor systems remain external factual truth.
4. gstack context-save/context-restore supplies semantic working context only; it cannot authorize production implementation resume.

## Runtime layout

```text
PREOS_STATE_ROOT/
  projects/
    <project-id>/
      production/
        PIPELINE-STATE.json
        CURRENT-STATE.json
        implementation-ledger.jsonl
        approval-state.json
        evidence-index.json
        evidence-records/
        recovery-events.jsonl
        checkpoints/
```

For schema-v1.2 runtime state, `PIPELINE-STATE.json`, `CURRENT-STATE.json`/checkpoints and the ledger are reconciled as one governed execution record. A contradictory, missing or malformed persisted view is not silently ignored.

## Checkpoints

Use `scripts/checkpoint-state.py` at meaningful transitions. Soft checkpoints persist runtime state and ledger events without creating a Git commit. Hard checkpoints are allowed only at a coherent verified boundary with a clean working tree; the helper records Git state but never commits or pushes automatically.

If the active AI Task Packet declares required checks or evidence, a hard checkpoint requires `--verification-manifest`. PREOS verifies that declared checks have machine-readable PASS/NOT_APPLICABLE results, referenced evidence IDs exist and are current, traceability status is recorded, and an explicit rollback point exists. This prevents a prose statement such as "tests passed" from being the sole proof for a declared hard boundary.

Prefer event-based checkpoints over arbitrary time intervals. A timer can preserve a half-written invalid state.

## Approval persistence

Use `scripts/record-approval.py` for consequential decisions that must survive session loss. `PENDING` remains pending after restart. AI/Codex/gstack/PREOS cannot grant consequential human approval. Approval ledger events use the canonical `APPROVAL_REQUIRED` and `APPROVAL_RECEIVED` vocabulary.

## Evidence freshness

Use `scripts/capture-evidence.py` for production evidence that must survive and be revalidated across sessions. Current production evidence can bind to:

- source files/hashes;
- Project Contract;
- AI Task Packet;
- Git commit/HEAD;
- selected environment variables through a non-secret fingerprint;
- configuration files;
- schema files;
- dependency/version files;
- test-definition files;
- validity period.

A change to any bound input makes that evidence stale. The selected environment-variable values are hashed and are not written into PREOS state. `scripts/validate-evidence.py --require-complete-bindings` proves the complete production freshness-binding vocabulary; default structural validation remains available for deliberately synthetic organizational acceptance records that must not be misrepresented as production evidence.

## Recovery

Use `scripts/recover-state.py <project-id> --repo <application-repo>` before resuming interrupted production-relevant implementation.

Recovery validates and reconciles:

- JSON runtime records against PREOS-owned schemas;
- `PIPELINE-STATE.json` against the newest checkpoint/`CURRENT-STATE.json`;
- ledger JSONL parse, event IDs, chronological sequence, canonical event vocabulary and checkpoint references;
- Project Contract/task-packet bindings;
- authoritative Project Contract source hashes when they resolve locally;
- Git repository, branch, HEAD and exact changed-file fingerprints;
- persisted approval state;
- all supported evidence freshness bindings;
- pending migration/test/build/evidence state;
- last verified action and the **first unverified action**, recorded as `next_unverified_action`.

A recovery result is one of:

- `SAFE_TO_RESUME` — resume from the first unverified action (`next_unverified_action`); revalidate stale evidence first when reported.
- `BLOCKED` — a persisted prerequisite such as human approval is still pending.
- `RECOVERY_CONFLICT` — state and reality disagree; stop coding until reconciled.

Do not resume from the last conversational topic. Do not silently discard dirty/untracked files. Do not trust a checkpoint claim when Git/source/evidence bindings changed.

## Recovery conflict examples

- wrong repository;
- branch or HEAD mismatch;
- working-tree fingerprint mismatch;
- Project Contract/task packet changed;
- authoritative source hash changed/missing;
- `PIPELINE-STATE.json` disagrees with checkpoint/current state;
- corrupt or schema-invalid state/checkpoint/approval/evidence index;
- unknown ledger event, duplicate ledger event ID, backwards ledger timestamp, missing checkpoint reference or invalid state transition;
- environment/config/schema/dependency/test-definition evidence binding changed;
- pending migration whose external state is uncertain;
- pending approval was lost or contradicted.

## Fresh-session interaction

A user may say `start from the last session`. The PREOS skill should identify the project, run deterministic recovery, summarize the pipeline state, last verified action and first unverified action, preserve pending approvals, and refuse implementation if the result is `RECOVERY_CONFLICT`.
