# Codex + gstack Skill System Architecture for PREOS

Date of design: 2026-08-24

## Purpose

PREOS must not become one giant skill. Keep one shared project state and a small number of stage-oriented skills, each loading only the references relevant to its current task. The original 75 controls remain the deterministic minimum baseline; context-generated risks, architecture/economic decisions, incidents, and current external research augment them.

## User-facing Codex workflow

```text
$project-init
  -> existing product/planning skills
  -> $risk-model
  -> $architecture-economics
  -> $production-plan
  -> human approval
  -> $production-implement
  -> existing $review
  -> existing $qa
  -> existing $ship / deployment / canary
  -> $production-learn
```

## Skill responsibilities

### $project-init
Creates or refreshes the Project Contract, source manifest and hashes, source authority map, product/business/architecture context, maturity stage, threat stage, jurisdiction/research flags, role availability, role gaps, and decision-rights matrix. Source conflicts and material UNKNOWNs block downstream mutation.

### $risk-model
Loads the approved Project Contract and generates material project risks with the combinatorial engine. It combines the 75 deterministic baseline, this atomic catalogue, project-specific features, architecture dependencies, human workflows, economics, and known incidents. It does not materialize an uncontrolled Cartesian product: it prioritizes single faults, high-coupling pairwise combinations, and 3-way combinations for high-consequence domains.

### $architecture-economics
Evaluates architectural options, unit economics, variable-cost drivers, cost concentration, economic-abuse surface, vendor concentration, complexity tax, migration paths, maturity triggers, and the Deferred Complexity Registry. It may recommend simple architecture and explicitly reject premature complexity.

### $production-plan
Transforms approved requirements + architecture + risks + 75 controls into Implementation Units. Each unit maps requirement -> risk -> control -> code surface -> test -> evidence -> monitoring -> rollback/recovery -> owners/approvers. No unit is READY while required risk or control classification is blank, RED, UNKNOWN, or awaiting HUMAN REVIEW.

### $production-implement
Implements only approved coherent units. Revalidates Project Contract hashes and plan scope, performs change-impact analysis, classifies all 75 baseline controls, runs relevant contextual risks, implements, self-attacks, tests, stores evidence, checkpoints, and stops on authority gates. It may say IMPLEMENTATION COMPLETE but never PRODUCTION APPROVED.

### $production-learn
Consumes incidents, postmortems, security findings, support escalations, cost anomalies, reliability events, and customer harm. It appends new atomic risk rules, regression tests, monitoring requirements, runbook changes, evidence invalidation rules, and architecture review triggers. It never deletes historical incident/risk evidence.

## Shared state

Version-controlled project state should contain sanitized governance and evidence indexes; user runtime state should contain resumable execution state, approvals, append-only ledger events, and recovery events. Conversation memory is never authoritative state.

Recommended project tree:

```text
.gstack/project-contract/
.gstack/preos/
  risk-model/
  architecture-decisions/
  deferred-complexity/
  evidence/
  incidents/
  traceability/
```

Recommended runtime tree:

```text
${GSTACK_STATE_ROOT}/projects/<slug>/production/
  PIPELINE-STATE.json
  CURRENT-STATE.json
  implementation-ledger.jsonl
  approval-state.json
  evidence-index.json
  recovery-events.jsonl
  checkpoints/
```

## Codex host integration rules

- Author canonical gstack skill sources in `.tmpl` and supporting reference/schema/script files, never by editing generated Codex `SKILL.md` files.
- Current gstack Codex host generation uses `.agents/skills/gstack-*` output directories, preserves skill frontmatter names, rewrites `CLAUDE.md` references to `AGENTS.md`, and generates `agents/openai.yaml` metadata. Re-inspect the upstream host config before each major integration because gstack evolves.
- Globally install only with the Codex host target after tests and explicit approval.
- Keep the user-visible skill name short and explicit; the generated directory may be prefixed `gstack-` while Codex explicit invocation resolves the frontmatter skill name.
- Use progressive disclosure: `SKILL.md.tmpl` contains purpose/routing/invariants; large taxonomies, the 75 controls, schemas and domain procedures live in references; deterministic state validation lives in scripts.

## Non-negotiable authority boundary

Codex may analyze, propose, implement approved scope, test, measure, generate evidence, recommend and escalate. It may not accept material risk, approve its own security/privacy/legal/financial exception, waive failing gates, expand architecture or scope silently, introduce paid vendors without authority, mutate production data without authority, or declare compliance / PRODUCTION APPROVED.

## Minimum deterministic tests of the skill system

1. All 75 baseline controls exist exactly once and retain wording/numbering.
2. No code mutation without a current approved Project Contract and approved plan.
3. UNKNOWN never becomes GREEN automatically.
4. HUMAN REVIEW persists across crash/restart.
5. Evidence has source, environment, commit/config binding and invalidation rules.
6. Stale source hashes invalidate impacted contract/risk/evidence state.
7. A RED critical risk blocks completion unless an authorized, expiring acceptance exists.
8. Risk acceptance includes authority, reason, scope, expiration, review trigger and compensating control.
9. Deferred complexity includes a measurable activation trigger and migration path.
10. Economic-abuse tests can flag a feature whose attacker marginal cost is materially below defender variable cost.
11. Recovery resumes at the first unverified action and detects dirty-tree disagreement.
12. Stage 5 cannot self-certify PRODUCTION APPROVED.
13. Codex host generation includes every new skill and valid `agents/openai.yaml` metadata.
14. Existing gstack test suite remains green.
