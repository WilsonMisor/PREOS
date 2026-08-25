# PREOS

**Production Risk, Economics, and Evolution Operating System**

PREOS is the production-assurance plane of an integrated software delivery system designed to produce applications that survive real-world use by both legitimate and malicious users.

PREOS is integrated with, but does not replace:

- **AI Product Delivery Blueprint**: `WilsonMisor/wed_dev_skill`, lifecycle governance, requirements, architecture, profiles, traceability and human gates.
- **gstack**: `WilsonMisor/gstack`, specialist engineering workforce.
- **Codex**: bounded implementation engine.
- **Application repositories**: actual product code and project-specific governed state.
- **Humans**: consequential authority, risk acceptance and production approval.

See `INTEGRATION-CONTRACT.md` and `ARCHITECTURE.md` for the authority and data-flow model.

## Canonical source corpus

The repository directly preserves and validates the source package:

- 75 deterministic baseline controls.
- 1,130 atomic risk records across 52 production domains, stored as deterministic gzip streams for bounded repository size and exact decompression.
- 1,300 production-readiness questions.
- Atomic risk JSON schema.
- Production risk/economics/evolution operating-system document.
- Virtual team ownership and decision-authority matrix.
- Original Codex + gstack PREOS architecture proposal.
- The exact original ZIP and its individual source files with SHA-256 provenance.

The 75 controls remain the deterministic minimum. Context-generated risks supplement them; they do not replace them.

## PREOS stage skills

1. `$preos-project-init`
2. `$preos-risk-model`
3. `$preos-architecture-economics`
4. `$preos-production-plan`
5. `$preos-production-implement`
6. `$preos-production-learn`

Use `$preos` as the router.

## Core rules

- Project Contract compiles and hashes approved Blueprint truth; it never competes with PRD/SRS/SRD.
- Risk modelling runs repeatedly: initial, post-architecture, task delta, release aggregation and incident-learning passes.
- `UNKNOWN` never silently becomes `GREEN`.
- `GREEN` requires current evidence.
- RED/UNKNOWN prerequisite controls contaminate dependent claims.
- Evidence becomes stale when bound code, configuration, environment, schema, dependency or assumption changes.
- Accepted risk requires accountable human authority, bounded scope, reason, expiration and review trigger.
- Missing human authority remains a `ROLE GAP`; AI and gstack personas cannot impersonate it.
- Deferred complexity requires measurable activation and review triggers.
- PREOS state uses `.ai-product-delivery/preos/` and `PREOS_STATE_ROOT`, never `.gstack/preos/` or `GSTACK_STATE_ROOT`.
- PREOS selects a bounded risk/readiness subset instead of loading the entire catalogue into model context.
- Production approval is a human decision.

## Validation

```bash
python scripts/validate-preos.py
python -m unittest discover -s tests -p 'test_*.py'
```

CI runs the same integrity and semantic checks on pushes and pull requests.
