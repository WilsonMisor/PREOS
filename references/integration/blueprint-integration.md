# Blueprint Integration

The AI Product Delivery Blueprint is the governing lifecycle and source of approved product truth. PREOS is an assurance overlay.

## Activation

Blueprint Project Classification selects PREOS assurance level: `inactive`, `lightweight`, `standard`, or `high-assurance`, and records maturity stage 0-5, threat stage, financial consequence, personal/sensitive data, multi-tenancy, money movement, critical operations, vendor reliance and regulatory exposure.

## Routing

- After Project Classification: `$preos-project-init`.
- After PRD/classification and again after material architecture change: `$preos-risk-model`.
- During architecture: `$preos-architecture-economics` plus `gstack-plan-eng-review`.
- Before each substantial implementation packet: PREOS risk delta and `$preos-production-plan`.
- During approved implementation: `$preos-production-implement`.
- Before release: PREOS G0-G11 evaluation, then human production authority.
- After incidents, releases, material telemetry/cost findings: `$preos-production-learn`, then Blueprint change control.

PREOS does not rewrite approved product requirements. A Project Contract hash change makes affected PREOS evidence and assessments candidates for invalidation/review.
