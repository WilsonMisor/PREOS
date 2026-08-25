# Contributing to PREOS

PREOS changes are governance changes. Treat them more strictly than ordinary documentation edits.

1. Work on an isolated branch or fork, never directly on protected `main` for substantial changes.
2. State the source concept, risk, control, gate, or integration contract being changed.
3. Do not delete or weaken the canonical 75 controls or source risk catalogue without an explicit migration/version decision.
4. Preserve stable IDs. If an ID must change, provide a migration map.
5. Update `RECOMMENDATION-COVERAGE.md`, `SOURCE-CONCEPT-COVERAGE.md`, manifests, schemas, tests, and documentation when affected.
6. Run `python scripts/validate-preos.py` and `python -m unittest discover -s tests -p 'test_*.py'`.
7. Any change to authority, gate semantics, evidence freshness, risk acceptance, production deployment, or source integrity requires explicit human review.
8. Do not vendor Blueprint or gstack source code into PREOS merely for integration.
