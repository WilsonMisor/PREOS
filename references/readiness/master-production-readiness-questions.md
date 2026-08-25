# Master Production Readiness Question Bank

The complete authoritative 1,300-question bank is preserved byte-for-byte inside `source-package/original-package.zip` as `master_production_readiness_questions.md`.

PREOS does not copy all 1,300 questions into ordinary model context. `scripts/select-readiness.py` reads the authoritative bank from the source package and selects only questions relevant to the Project Contract, active profiles, task, changed components and current risks.

Use:

```bash
python scripts/extract-source.py master_production_readiness_questions.md
```

to materialize the exact source document locally when full human review is required.
