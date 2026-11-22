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
