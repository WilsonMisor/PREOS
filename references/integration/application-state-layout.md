# Application State Layout

Use one governed root in each application repository:

```text
.ai-product-delivery/
├── project-contract/
├── task-packets/
├── approvals/
└── preos/
    ├── risk-model/
    ├── control-assessments/
    ├── architecture-economics/
    ├── deferred-complexity/
    ├── gate-state/
    ├── evidence/
    ├── risk-acceptance/
    ├── incidents/
    └── traceability/
```

Do not place PREOS project truth under `.gstack/`. gstack is a specialist tool, not the owner of production-assurance state.

Resumable runtime state belongs under `PREOS_STATE_ROOT/projects/<project-id>/production/` with `PIPELINE-STATE.json`, `CURRENT-STATE.json`, `implementation-ledger.jsonl`, `approval-state.json`, `evidence-index.json`, `recovery-events.jsonl` and `checkpoints/`.
