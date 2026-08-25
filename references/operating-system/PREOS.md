# PREOS Source Operating System

The complete authoritative source document is preserved byte-for-byte inside `source-package/original-package.zip` as `production_risk_economics_evolution_operating_system.md`.

Use:

```bash
python scripts/extract-source.py production_risk_economics_evolution_operating_system.md
```

or read it directly through Python's `zipfile` module. PREOS deliberately keeps this long source document in the provenance package so source fidelity is hash-verifiable and there is no second editable copy that can drift.

`SOURCE-CONCEPT-COVERAGE.md` is the semantic coverage ledger for every operating-system concept integrated into the executable PREOS layer. It does not replace the authoritative source text.
