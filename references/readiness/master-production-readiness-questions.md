# Master Production Readiness Question Bank

The complete authoritative 1,300-question bank is the source-package member `master_production_readiness_questions.md`. The exact original package is stored as checksum-verified base64 chunks under `source-package/package-chunks/` and reconstructed byte-for-byte by PREOS.

PREOS does not copy all 1,300 questions into ordinary model context. `scripts/select-readiness.py` reads the authoritative bank from the reconstructed source package and selects only questions relevant to the Project Contract, active profiles, task, changed components and current risks.

Use:

```bash
python scripts/extract-source.py master_production_readiness_questions.md
```

to materialize the exact source document locally when full human review is required.
