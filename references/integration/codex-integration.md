# Codex Integration

Codex is the implementation engine. PREOS does not create an independent implementation unit that competes with the Blueprint AI Task Packet.

## Enriched AI Task Packet

A substantial packet may include:

- Blueprint requirement IDs;
- PREOS risk IDs;
- baseline/control IDs;
- related ADR and deferred-complexity IDs;
- allowed code/config/data surface;
- prohibited actions;
- positive, negative, permission, cross-tenant, concurrency, retry/duplicate, provider-failure, migration/rollback, restore, reconciliation, invariant, load and cost tests as applicable;
- evidence requirements;
- monitoring and alert requirements;
- recovery and reconciliation requirements;
- economic impact and activation triggers;
- gstack reviewer routes;
- human approver and production authority.

Codex must make the smallest coherent approved change and cannot use PREOS as permission to broaden scope into speculative hardening.
