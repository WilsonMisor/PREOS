# PAS v2 continuation evidence

This continuation preserves the Phase 10 and published PAS v2 ancestry on
`pasv2/final-residual-remediation`. Model 2 remains installed but non-default;
`PREOS_MODEL2_CROSSWALK_APPROVAL` is still a human decision.

Cross-repository execution evidence is maintained at the programme root in
`.migration-control/pasv2-codex-finalization/`. Its source audit, exact test logs,
requirement register, recovery inventory, installation verification and final
Git publication report are packaged in
`PASV2-CODEX-FINALIZATION-AUDIT-BUNDLE.zip` outside the repositories. Final commit
identities and bundle hashes belong there to avoid a self-referential commit.

Repository checks remain executable: `scripts/four_source_audit.py`,
`scripts/validate-preos.py`, `scripts/build_codex_distribution.py --check`,
and `python -m pytest tests`. Passing technical checks does not approve the
semantic review queue, human risk acceptance, or production release.

The bounded successor audit is at programme-root
`.migration-control/pasv2-codex-finalization-v2/` and in
`PASV2-CODEX-FINALIZATION-AUDIT-BUNDLE-v2.zip`. It closes four independently
reported gaps: project-independent RiskDefinition, explicit RiskAssessment
scope, structurally complete RiskAcceptance, and mandatory schema validation
of all six concerns before lifecycle validation. The 4,210 normalized
definitions are preserved byte for byte. The earlier bundle and its evidence
remain historical records; the successor re-evaluates MP-REQ-00097,
MP-REQ-00098 and MP-REQ-00102 using new adversarial tests and a separate
Draft 2020-12 validator. Runtime validation remains dependency-free;
`requirements-test.txt` supplies the independent test oracle.
