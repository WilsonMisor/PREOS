# PREOS Integration Recommendation Coverage

This ledger prevents semantic omissions. A recommendation is complete only when the implementing behavior exists, not merely a similarly named file.

| ID | Integration recommendation | Evidence | Status |
|---|---|---|---|
| I01 | PREOS is a third major assurance layer integrated with Blueprint, gstack and Codex, not loose documentation. | `SKILL.md; ARCHITECTURE.md` | REQUIRED |
| I02 | PREOS is an assurance overlay, not a Web/WordPress/SaaS/Mobile/API/Data/Infrastructure project profile. | `references/integration/blueprint-integration.md` | REQUIRED |
| I03 | Keep the three systems separately versioned and integrate by contracts rather than repository fusion. | `ARCHITECTURE.md; AGENTS.md` | REQUIRED |
| I04 | Reorganize the package into skills, references, schemas, scripts, templates, tests and provenance. | `preos tree` | REQUIRED |
| I05 | Keep the 75 controls in one canonical location and assess rather than duplicate them per app. | `references/baseline; validate-baseline.py` | REQUIRED |
| I06 | Keep the 1,130 atomic risks as a production engineering knowledge base and select subsets rather than loading everything. | `references/risks; select-risks.py` | REQUIRED |
| I07 | Use PREOS to address real-world failure, economic and operational questions beyond build correctness. | `PREOS.md; SKILL.md` | REQUIRED |
| I08 | Add Blueprint PREOS routing and production-assurance activation. | `references/integration/blueprint-integration.md` | REQUIRED |
| I09 | Make PREOS activation risk/maturity based rather than universally maximal. | `preos-project-init/SKILL.md` | REQUIRED |
| I10 | Use six namespaced stage skills. | `six preos-* skills` | REQUIRED |
| I11 | Do not let Project Contract duplicate PRD/SRS/SRD; compile/hash approved truth. | `preos-project-init/SKILL.md; schema` | REQUIRED |
| I12 | Use source hashes for drift detection and invalidate/review affected assurance. | `hash-sources.py; change-impact.py` | REQUIRED |
| I13 | Run risk modeling multiple times: Pass A, Pass B, task delta, release pass, learning pass. | `SKILL.md; preos-risk-model` | REQUIRED |
| I14 | Integrate architecture economics into the architecture gate. | `preos-architecture-economics` | REQUIRED |
| I15 | Use Deferred Complexity Registry to block AI overengineering without measurable activation triggers. | `schema/template; architecture-economics` | REQUIRED |
| I16 | Merge PREOS Implementation Unit concept into the Blueprint AI Task Packet rather than create two units. | `schemas/implementation-unit.schema.json; production-plan` | REQUIRED |
| I17 | Keep gstack as the specialist virtual engineering team and route PREOS needs to exact namespaced specialists. | `references/integration/gstack-integration.md` | REQUIRED |
| I18 | Use the full closed-loop lifecycle from idea through production learning and controlled change. | `ARCHITECTURE.md` | REQUIRED |
| I19 | Preserve G0-G11 as final production-assurance gates over the 75-control baseline. | `references/gates` | REQUIRED |
| I20 | Keep deterministic gate states and UNKNOWN != GREEN. | `evaluate-gates.py; SKILL.md` | REQUIRED |
| I21 | Implement control dependency contamination so downstream GREEN cannot survive RED/UNKNOWN prerequisite. | `preos-risk-model; gate semantics` | REQUIRED |
| I22 | Make evidence freshness and invalidation first-class. | `evidence schema; invalidate-stale-evidence.py` | REQUIRED |
| I23 | Never replace required human authority with gstack or AI personas; use ROLE GAP. | `AGENTS.md; validate-role-authority.py` | REQUIRED |
| I24 | Store project governance under .ai-product-delivery/preos, not .gstack/preos. | `application-state-layout.md; init-project-state.py` | REQUIRED |
| I25 | Use PREOS_STATE_ROOT, not GSTACK_STATE_ROOT, for resumable PREOS runtime state. | `application-state-layout.md; preos_common.py` | REQUIRED |
| I26 | Maintain three classes of state: version-controlled project truth, resumable PREOS runtime state, external production truth. | `ARCHITECTURE.md` | REQUIRED |
| I27 | Treat the 1,300 readiness questions as a selectively routed bank, not a giant prompt. | `SKILL.md; risk-model` | REQUIRED |
| I28 | Extend traceability to Requirement -> Risk -> Control -> Task Packet -> Code -> Test -> Evidence -> Monitor -> Recovery/Incident -> Regression. | `production-plan; source PREOS` | REQUIRED |
| I29 | Perform change-impact analysis before implementation and after upstream drift. | `change-impact.py` | REQUIRED |
| I30 | Do not substantially modify gstack core; integrate through specialist contracts. | `gstack integration reference` | REQUIRED |
| I31 | Add explicit PREOS routing to the Blueprint. | `blueprint integration reference` | REQUIRED |
| I32 | Let PREOS determine assurance needed and gstack determine specialist execution. | `gstack integration reference` | REQUIRED |
| I33 | Preserve clean human/Blueprint/PREOS/gstack/Codex/application authority layering. | `ARCHITECTURE.md` | REQUIRED |
| I34 | Add machine integrity checks for controls, risks, evidence, dependencies, authority, acceptance and state. | `scripts/tests` | REQUIRED |
| I35 | Preserve original package provenance with hashes and counts. | `source-package/PACKAGE-CHUNKS.json`, `source-package/package-chunks/`, `scripts/reconstruct-source-package.py` | REQUIRED |
| I36 | Use safe stacked/isolated branches and draft PR review before integration. | `GitHub integration strategy and docs` | REQUIRED |
| I37 | Keep PREOS installable beside namespaced gstack Codex skills. | `install-codex scripts; agents` | REQUIRED |
| I38 | Treat all three as one operational software production system whose goal is production-ready software resilient to good and malicious users. | `README.md; SKILL.md` | REQUIRED |
