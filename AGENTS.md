# PREOS Agent Rules

## Authority

PREOS is an assurance system, not an autonomous risk authority. AI may analyze, select risks, propose contextual risks, implement approved task packets, execute tests, collect evidence and recommend gate outcomes. AI may not:

- accept material risk;
- waive RED, HUMAN REVIEW or UNKNOWN findings;
- approve its own security, privacy, legal, financial or compliance exception;
- declare compliance without qualified human authority;
- silently add paid vendors or external spend;
- mutate production data without explicit delegated authority;
- broaden approved scope or architecture;
- perform irreversible production release without explicit human approval.

## Integration contract

1. Read Blueprint-approved artifacts before PREOS analysis.
2. Treat the Project Contract as a compiled hash-bound snapshot, not a competing PRD/SRS/SRD.
3. Route specialist challenge and verification to namespaced gstack skills.
4. Use Blueprint AI Task Packets as the canonical implementation unit; PREOS extends them rather than inventing a competing work object.
5. Persist project state under `.ai-product-delivery/preos/`, never `.gstack/preos/`.
6. Persist resumable PREOS runtime state under `PREOS_STATE_ROOT`, never `GSTACK_STATE_ROOT`.
7. Do not ask all 1,300 readiness questions blindly. Select by Project Contract, active profiles, task, changed components and current risks.
8. Never load all 1,130 atomic risks into model context when a selected subset suffices.
9. Every GREEN claim must have current evidence.
10. Every accepted risk must name human authority, reason, scope, expiration and review trigger.
