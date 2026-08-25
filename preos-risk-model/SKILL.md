---
name: preos-risk-model
description: Apply the exact PREOS 75-control baseline, select relevant atomic risks/readiness questions, generate contextual risk candidates, evaluate control dependencies, and create risk deltas without loading the full corpus unnecessarily.
---
# PREOS Risk Model

Inputs are the current PREOS Project Contract plus Blueprint requirements/architecture and, for deltas, the current AI Task Packet/change surface.

1. Always preserve the canonical 75 controls as the deterministic minimum. Do not duplicate or renumber them.
2. Select from the 1,130 atomic risks by active profiles, feature, actors, changed components, maturity/threat stage and risk relationships. Use `../preos/scripts/select-risks.py` and `generate-context-risks.py` as deterministic bounded selectors.
3. Select only relevant questions from the 1,300-question bank. Unanswered material questions remain UNKNOWN.
4. Run risk Pass A after PRD/classification, Pass B after architecture, a risk delta before each substantial task packet, a release pass before production, and a learning pass after incidents/material findings.
5. Model interactions: retries + money, caching + authorization, queues + idempotency, mobile-version lag + API change, tenant concentration + resource limits, vendors + failure/cost, configuration + rollout, and other context-specific combinations.
6. Build control dependencies. A downstream GREEN claim cannot survive a RED or UNKNOWN prerequisite.
7. Aggregate release risk without averaging away critical findings. RED, HUMAN REVIEW and UNKNOWN remain visible.
8. Route security/architecture specialist review to `gstack-cso` and `gstack-plan-eng-review` when triggered, passing requirement/risk/control IDs.
9. Output selected catalogue IDs, context-generated candidate IDs, 75-control applicability state, dependency changes, release-risk contribution, UNKNOWN/HUMAN REVIEW/ROLE GAP items and next route.
