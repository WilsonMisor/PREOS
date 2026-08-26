# AI Session Continuity, Checkpoints, and Recovery

PREOS treats loss of the AI coding session as a production-process failure mode. The development system must remain recoverable after Codex context loss, process/terminal/network interruption, deliberate stop, or PC restart.

## Doctrine

Conversation memory is never authoritative execution state.

The continuity model has four layers:

1. Blueprint/application governance under `.ai-product-delivery/` establishes approved source authority, requirements, architecture, task packets and approvals.
2. PREOS runtime state under `PREOS_STATE_ROOT` establishes the last verified execution state, checkpoints, ledger, approvals and evidence index.
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
        recovery-events.jsonl
        checkpoints/
```

## Checkpoints

Use `scripts/checkpoint-state.py` at meaningful transitions. Soft checkpoints persist runtime state and ledger events without creating a Git commit. Hard checkpoints are allowed only at a coherent verified boundary with a clean working tree; the helper records Git state but never commits or pushes automatically.

Prefer event-based checkpoints over arbitrary time intervals. A timer can preserve a half-written invalid state.

## Approval persistence

Use `scripts/record-approval.py` for consequential decisions that must survive session loss. `PENDING` remains pending after restart. AI/Codex/gstack/PREOS cannot grant consequential human approval.

## Recovery

Use `scripts/recover-state.py <project-id> --repo <application-repo>` before resuming interrupted production-relevant implementation.

Recovery reconciles:

- Project Contract/task-packet bindings;
- authoritative Project Contract source hashes when they resolve locally;
- Git repository, branch, HEAD and exact changed-file fingerprints;
- persisted approval state;
- evidence bindings/freshness;
- last verified action and the **first unverified action**, recorded as `next_unverified_action`.

A recovery result is one of:

- `SAFE_TO_RESUME` — resume from the first unverified action (`next_unverified_action`); revalidate stale evidence first when reported.
- `BLOCKED` — a persisted prerequisite such as human approval is still pending.
- `RECOVERY_CONFLICT` — state and reality disagree; stop coding until reconciled.

Do not resume from the last conversational topic. Do not silently discard dirty/untracked files. Do not trust a checkpoint claim when Git/source/evidence bindings changed.

## Recovery conflict examples

- wrong repository;
- branch mismatch;
- HEAD mismatch;
- working-tree fingerprint mismatch;
- Project Contract/task packet changed;
- authoritative source hash changed/missing;
- corrupt state/checkpoint/approval/evidence index;
- evidence is incompatible with current bindings;
- pending approval was lost or contradicted.

## Fresh-session interaction

A user may say `start from the last session`. The PREOS skill should identify the project, run deterministic recovery, summarize the last verified action and first unverified action, preserve pending approvals, and refuse implementation if the result is `RECOVERY_CONFLICT`.
