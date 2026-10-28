# PAS v2 controlled implementation changes

Scope authority: the user-invoked implementation-first prompt and governing
master SHA-256 `74e547225f0af2e0f64d0930f7f4317e86823bf6b103c96f648936b1dfa823c3`.
Phase-10 predecessor `c15176e104278405e93587da291b50f42126023a` remains an ancestor.
The audited candidate and later work are preserved in Git history.

## Candidate promotion

`scripts/candidate_workflow.py submit candidate.json --queue <project-candidate-directory>`
records source/incident/generated candidates independently of the canonical
corpus. The Python `prepare_promotion` API checks semantic fields, deduplication,
source hashes, version progression and the exact regression method. Its returned
scope hash is the scope required by a durable `CANONICAL_RISK_PROMOTION` decision
in the existing PREOS approval-state format.

`promote` consumes that approval; it does not create approvals. It executes the
bound regression, validates the canonical schema and relationship endpoints,
writes an immutable version and its audit, and atomically replaces `CURRENT.json`.
The source catalogue remains unchanged. Every promotion retains a distinct
candidate ID and canonical ID. New versions remain installed-not-default;
promotion does not close the existing Model2 activation gate.

The old `pasv2_runtime.promote_candidate_risk` caller-boolean API is intentionally
disabled. Its earlier return value was only a plan, and its `qualified_human`
flag did not represent durable authority. Tests now require rejection of that
shortcut and exercise actual isolated publication via the canonical workflow.

## Five-engine behavior

`assurance_engines.py` owns deterministic context normalization, bounded
catalogue-first risk selection and pairwise adversity generation, dimensional
cost calculations, and measurable evolution triggers. Missing dimensions remain
UNKNOWN; false values remain known false. Caller assumptions require provenance,
an owner and a validation trigger. Existing catalogue semantic-review status is
not promoted by contextual selection.

`control_assurance.py` maps Source-4 nondeferrable controls to the actual immutable
FS control meanings. For example TLS maps to FS-003 and tenant isolation includes
FS-074. NDC identifiers express narrower Source-4 evidence obligations without
renumbering or replacing the original 75 controls. A later production release
does not exempt the same controls. Small product/team size is not an exemption.

Evidence capture runs an exact unittest method and binds its output to code,
tests, Git and environment. Gate evaluation checks those bindings and artifact
integrity. A CURRENT string is insufficient. Technical gates cannot authorize
production, and acceptance expiry/revocation uses the existing concern runtime.

## Validation and rollback

Behavioral regression suites: `test_candidate_workflow.py`,
`test_assurance_engines.py`, and `test_control_evidence.py`. The original corpus,
sentinel corrections, original controls, source hashes, and concern separation
remain subject to the existing tests.

Rollback uses the preceding Git commits and previous immutable catalogue version.
Do not delete candidate history or infer approval during rollback. A definition
correction or changed regression invalidates the proposed promotion scope and
requires fresh review. No production release or Model2 default activation is
authorized by these changes.
# Resolvable project graph and incident learning

The benchmark command is `python scripts/assurance_benchmark.py --output <file>`.
It measures a cold graph query, bounded selection, context generation,
serialization/compression, source validation, Python allocation peak, and an
actual engine test subprocess. All nine budgets in
`references/integration/performance-budgets.json` are enforced. Allocation peak
is explicitly distinguished from operating-system RSS; a source checkout is
required for the representative CI tests.

`scripts/risk_graph.py` resolves canonical relationship endpoints before query.
Context hints do not establish mitigation, gates, evidence or incidents. Those
queries remain empty until a project supplies validated lifecycle links.

`python scripts/pasv2_runtime.py validate-project-trace <project/graph.json>`
checks artifact identities, content hashes, exact Python symbols, actual test
calls, executed evidence, project/release scopes and joins across the declared
edges. `query-graph --type evidence --project-graph <project/graph.json>` consumes
the same validator. The generated catalogue-level historical traceability still
needs the separate source-unit migration; a project graph does not prove it.

Incident learning uses `scripts/production_feedback.py`. All twelve Source-4
feedback actions require recorded results or, for conditional architecture,
cost and security updates, an explicit rationale and review trigger. Tests,
monitoring and runbook references resolve to current project files. Proposed
risks enter the existing candidate queue and cannot mutate the canonical corpus.

`source-package/four-sources` preserves the four governing inputs as gzip files.
`python scripts/canonical_sources.py` verifies archive hashes and decompressed
bytes against the immutable input hashes. This works outside the migration
workspace. Tests cover corruption and manifest tampering.

