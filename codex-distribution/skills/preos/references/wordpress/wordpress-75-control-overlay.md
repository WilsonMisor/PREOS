# WordPress Classic Theme + Custom Plugin Interpretation of FS-001..FS-075

This is an **interpretation overlay**, not a second baseline. Canonical control identity and generic meaning remain in the immutable PREOS 75-control source. When the Blueprint activates the WordPress classic-theme/custom-plugin profile, apply the corresponding WordPress gate, test and evidence below to each applicable control.

Core boundary: classic theme owns presentation; custom plugin owns application/business logic. WordPress core is the CMS runtime and hosting is the runtime environment. Native MySQL row-level security is not assumed; private/multi-user data must be protected with capability, ownership, tenant/organisation, status and `WHERE`-scoped enforcement at every entry point.

## A. HTTP, APIs, contracts and protocol behaviour — FS-001..FS-014

| Control | WordPress gate | WordPress test | Expected evidence |
| --- | --- | --- | --- |
| FS-001 | Every form, admin-AJAX action or REST route defines fields, response, errors, nonce/auth context and permission callback before code. | Submit valid/invalid form, REST and AJAX payloads; verify response shape. | Form/route contract, nonce rule, `permission_callback`, test output. |
| FS-002 | Reads use GET; creates POST; updates PUT/PATCH where appropriate; deletes DELETE or protected admin action. | Try state-changing GET and direct admin URLs; they fail safely. | Handler/route table, direct-URL test, admin-action review. |
| FS-003 | Production forces HTTPS for public pages, wp-admin, REST, AJAX, login, forms, uploads and assets. | Request those surfaces over HTTP and confirm redirect/secure behavior. | Certificate, redirect rule, wp-admin HTTPS and header evidence. |
| FS-004 | Plugin validates `$_POST`, `$_GET`, REST params, AJAX payloads, files and settings before processing. | Send invalid inputs to each applicable entry point. | Validation functions/schema and failed-input tests. |
| FS-005 | REST/AJAX/form processors deliberately distinguish success, validation, auth, permission, not-found, conflict and server errors. | Force each error class. | Response samples, screenshots/log samples. |
| FS-006 | REST routes, AJAX handlers, forms, shortcodes, admin pages and settings have documented contracts. | Run contract checks after plugin update. | Plugin contract, workflow note, route list, update test. |
| FS-007 | Plugin updates preserve existing templates, data rows, settings, routes and admin workflows unless migration is approved. | Upgrade over existing data and exercise old paths. | Upgrade test, changelog, migration result. |
| FS-008 | Breaking route/schema changes use versioning or an explicit migration path. | Exercise old/new routes or migration paths. | Versioning/migration note and compatibility test. |
| FS-009 | `WP_Query`, custom-table lists, reports, admin tables and exports use limits/pagination. | Seed many rows/posts and page through frontend/admin/REST/export. | Query args, pagination config, limit test. |
| FS-010 | Fast-changing lists prefer cursor or stable-key pagination when offset paging can drift. | Insert rows while paging and verify stable results. | Cursor/stable-key design and test. |
| FS-011 | GET/public reads do not mutate posts/options/usermeta/custom tables or send email. | Repeat reads and compare DB/options/email state. | DB diff, email-log check, route review. |
| FS-012 | Forms, admin actions, payments/webhooks, imports, emails and cron use nonce plus idempotency/deduplication where repeat effects matter. | Refresh/replay/rerun and verify one business effect. | Nonce/idempotency rule, duplicate-submission/replay test. |
| FS-013 | REST, admin-AJAX or plain form POST is chosen by need; avoid needless API complexity. | Review the feature against the available WordPress mechanisms. | Architecture decision for chosen request style. |
| FS-014 | Requests remain valid across PHP workers/instances; avoid local-only process state. | Route requests across workers/instances where available. | Statelessness/shared-state decision and test. |

## B. Load balancing, scaling, queues and event flow — FS-015..FS-020

| Control | WordPress gate | WordPress test | Expected evidence |
| --- | --- | --- | --- |
| FS-015 | WordPress, uploads, sessions, cron, cache, REST and redirects work behind reverse proxy/CDN when used. | Exercise login, REST, upload, admin, redirects and cache through proxy/CDN. | Proxy/CDN config and smoke results. |
| FS-016 | Avoid local-only PHP-session assumptions; use WordPress cookies, transients, object cache or shared store intentionally. | Change worker or clear local PHP session and repeat flow. | Session decision and behavior test. |
| FS-017 | Slow email/import/export/image/report/integration/cleanup work uses cron, batch or queue-like processing when needed. | Trigger slow work and verify foreground request returns while background work completes. | Cron/batch handler, job log, timing. |
| FS-018 | Cron/background consumers tolerate duplicate runs/events. | Run same job/event twice and verify no duplicate records/emails/transitions. | Lock/dedupe rule and duplicate-run test. |
| FS-019 | Cron, webhooks, email, imports and background work define retry, lock, timeout and failure logging. | Force failure and verify bounded retry/lock/timeout/failure record. | Retry policy/config and logs. |
| FS-020 | Plugin hooks/actions or queue-like events fan out domain events without unnecessary tight coupling. | Fire one event and verify subscribers handle independently. | Hook/event map, payload and subscriber logs. |

## C. Data modelling, transactions, replication, sharding and storage — FS-021..FS-037

| Control | WordPress gate | WordPress test | Expected evidence |
| --- | --- | --- | --- |
| FS-021 | Decide posts/postmeta/options/users/usermeta/taxonomies/custom tables before storing data. | Run activation/migration and attempt invalid storage. | Storage decision, migration/activation proof, schema version. |
| FS-022 | Custom tables have stable primary keys; core records use correct post/user/term/meta identifiers. | CRUD/query records by stable IDs. | Schema/migration and CRUD test. |
| FS-023 | Where DB foreign keys are absent, plugin code enforces relationship integrity and cleanup/orphan rules. | Delete parent and verify cleanup/protection. | Relationship/cleanup rule and orphan test. |
| FS-024 | Custom-table constraints and plugin validation preserve invariants in tables/meta/options. | Attempt invalid options/meta/table rows/status transitions. | Constraints/validation and failed-write test. |
| FS-025 | Ownership/status/date/tenant/lookup/sort/pagination columns are indexed where growth requires it. | Run `EXPLAIN` or timings on heavy queries. | Index list, query plan/timing. |
| FS-026 | `WP_Query`, `meta_query`, admin lists, reports and exports avoid unbounded scans. | Seed large data and inspect query count/slow log. | Query Monitor/slow-log evidence and remediation. |
| FS-027 | Multi-step writes use `$wpdb` transactions where supported or compensating rollback. | Force failure mid-write and verify rollback/compensation. | Transaction/compensation code and failure test. |
| FS-028 | Approvals, bookings, imports, payments, counters and cron use locks, unique keys, version checks or idempotency as needed. | Execute concurrent/repeated operations. | Lock/unique/version/dedupe proof. |
| FS-029 | If read replicas exist, critical post-write flows know when to read primary. | Write then immediately read critical state. | Read-routing decision and stale-read test. |
| FS-030 | Recent writes do not disappear due to replica/cache/object-cache lag; user receives safe state. | Simulate lag/staleness. | Consistency rule, cache-clear evidence, safe-state UI. |
| FS-031 | Sharding/partitioning is not assumed; if scale demands it, justify custom architecture or moving that workload from WordPress. | Review WordPress suitability at projected scale. | ADR, scale warning and alternatives. |
| FS-032 | If custom sharding exists, shard key supports tenant/owner/date/common admin queries. | Simulate distribution and common query paths. | Shard-key decision and distribution/query test. |
| FS-033 | No tenant/user/date/status bucket should overload one custom storage segment. | Load-test skewed distributions. | Metrics/load test and mitigation. |
| FS-034 | Uploads use WordPress media or object storage where scale requires; large files do not live in postmeta. | Upload large file and inspect DB. | Media/object-storage config and metadata-only proof. |
| FS-035 | Media/custom file metadata tracks owner, key/attachment ID, MIME, size, visibility, status and timestamps. | List metadata without loading file bodies. | Metadata schema/row and listing test. |
| FS-036 | Filenames/object keys are sanitized and collision safe. | Upload same filename twice. | Sanitization/key logic and collision test. |
| FS-037 | Private uploads/exports/reports/generated files require capability and owner/tenant checks before download. | Attempt logged-out and wrong-user downloads. | Controlled/signed access and denial evidence. |

## D. Caching, CDN and proxy safety — FS-038..FS-050

| Control | WordPress gate | WordPress test | Expected evidence |
| --- | --- | --- | --- |
| FS-038 | Expensive queries/reports use object cache/transients when justified. | Measure repeated expensive operation before/after cache. | Cache rule, timings, hit ratio. |
| FS-039 | Cache keys include site/user/role/tenant/permission/filter/language/version dimensions where relevant. | Attempt cross-user/tenant/role/language/filter reuse. | Key format, isolation test, code review. |
| FS-040 | Transient/object/page/CDN caches have explicit freshness/TTL rules. | Inspect expiries and response headers. | TTL matrix/config/header evidence. |
| FS-041 | Writes/imports/deletes clear affected transient/object/page/CDN caches. | Change data and verify affected cache invalidates. | Invalidation hook/purge log/update test. |
| FS-042 | Hot rebuilds use locking/single-flight behavior to avoid stampedes. | Expire hot cache and send concurrent requests. | Lock code, concurrent result, query count. |
| FS-043 | Repeated missing slugs/IDs/search/private keys cannot hammer DB indefinitely. | Repeatedly request misses. | Negative cache/throttle rule, DB-hit/abuse log. |
| FS-044 | Large groups of caches/jobs do not expire/run simultaneously without intentional staggering. | Inspect expiry/scheduled distributions. | TTL jitter/schedule-spread evidence. |
| FS-045 | Cache eviction/flush is safe and rebuildable. | Flush/evict cache and repeat critical flow. | Safe-rebuild test and cache notes. |
| FS-046 | Theme assets/images/CSS/JS/public media are CDN-safe and versioned. | Load through CDN and inspect versions/headers. | CDN config, versioned enqueue, headers. |
| FS-047 | wp-admin, account pages, forms, carts, private dashboards and personalized pages bypass public cache. | Inspect cache behavior for private/personalized surfaces. | Bypass config/headers and leakage test. |
| FS-048 | Theme/plugin output sends/respects correct `Cache-Control` behavior. | Check public/private/REST/asset headers. | Header matrix and hosting cache note. |
| FS-049 | `home_url`, `site_url`, redirects, SSL detection, REST and asset URLs work behind proxy/CDN. | Exercise URL generation/redirects/REST/SSL behind proxy. | Trusted-proxy config and URL/SSL proof. |
| FS-050 | Only trusted proxy/CDN forwarded headers determine client IP/HTTPS/rate-limit identity. | Spoof forwarded headers. | Trusted-header policy, spoof test, access logs. |

## E. DNS, ports, network timeouts and data-style choices — FS-051..FS-057

| Control | WordPress gate | WordPress test | Expected evidence |
| --- | --- | --- | --- |
| FS-051 | Root/www/staging/API/CDN/mail/SSL DNS records target the correct environment. | Resolve relevant records. | DNS export/resolver output/environment map. |
| FS-052 | Staging and production separate URLs, DBs, uploads, cache, credentials and email behavior. | Submit staging workflow and prove production resources untouched. | Environment config, separate-DB proof, email policy. |
| FS-053 | Only required hosting ports are exposed; public/admin web traffic uses HTTPS. | Review firewall/panel or authorized port scan. | Firewall/panel/scan evidence. |
| FS-054 | `wp_remote_*`, imports, cron, uploads, REST and AJAX have timeouts and safe failure handling. | Simulate slow dependency/operation. | Timeout config, failure test, log. |
| FS-055 | Remote calls/cron/email/import/webhook retries are bounded, back off and are duplicate-safe. | Force failure/replay and verify limits/dedupe. | Retry config, dedupe test, logs. |
| FS-056 | Normal WordPress HTTP/TCP remains the default; WebSocket/UDP/real-time needs receive explicit separate architecture. | Review any real-time requirement independently. | Protocol decision/real-time design. |
| FS-057 | Posts/meta/options/custom tables/external SQL/NoSQL are selected by access pattern, not convenience. | Benchmark candidate storage against real access pattern. | Storage decision, access-pattern table, benchmark. |

## F. Availability, observability, testing, recovery, operations and security closure — FS-058..FS-075

| Control | WordPress gate | WordPress test | Expected evidence |
| --- | --- | --- | --- |
| FS-058 | Production has uptime, health, SSL, domain and admin-access recovery monitoring. | Disable a non-critical dependency / exercise health checks safely. | Uptime/health/SSL/domain monitoring evidence. |
| FS-059 | Capacity estimates include visits, forms, REST, cron, imports, exports and DB queries. | Load/traffic-test critical paths. | Load output, capacity assumptions, hosting metrics. |
| FS-060 | Measure public-page, REST, admin-list, form-submit and slow-query latency. | Repeatedly measure critical paths. | Latency report and slow-query/page-speed evidence. |
| FS-061 | PHP/WP/plugin/permission/email/job logs are useful and sanitized. | Trigger representative failures and inspect logs. | Sanitized samples/config/error records. |
| FS-062 | Hosting CPU/memory/PHP errors/DB load/cache hit rate/REST latency/failed jobs are observable where applicable. | Generate controlled load and inspect metrics. | Hosting/PHP/DB/cache metrics. |
| FS-063 | Uptime, SSL expiry, backup, form/email failure and fatal errors alert responsible people where applicable. | Trigger synthetic/test alert safely. | Alert rule, recipient and notification proof. |
| FS-064 | DB/uploads/theme/plugin/backups/email/DNS/hosting single points of failure are registered. | Review failure of each critical dependency. | SPOF register, backup/dependency review. |
| FS-065 | Backups/offsite copies/restore path/CDN/email fallback/hosting upgrade path exist where uptime requires them. | Restore/fail over using approved safe test path. | Offsite backup, restore result, upgrade/fallback path. |
| FS-066 | Validation, nonce, permission, DB, email, upload, cache, cron, REST and theme failure paths are tested. | Run applicable negative tests. | Negative-test checklist, screenshots/logs. |
| FS-067 | Page cache/CDN/object cache/form/API limits/hosting capacity are tested for traffic growth. | Load-test cached/uncached paths, forms, REST and admin as relevant. | Load report, cache behavior, rate-limit result. |
| FS-068 | Postmeta/options/custom tables/uploads/logs/admin screens/exports are tested with large data. | Seed large representative data and exercise workflows. | Seed tooling, Query Monitor/query-plan/export timings. |
| FS-069 | Site survives object-cache miss/outage, page-cache bypass, stale transient and CDN purge mistakes. | Disable/flush/expire cache safely in non-production. | Cache-failure test, fallback behavior, DB-load metric. |
| FS-070 | Failed plugin/theme upload, migration, cache problem, smoke-test failure and rollback are rehearsed. | Force safe staging deployment failure and recover. | Deployment log, rollback record, smoke result. |
| FS-071 | Major classic-theme/plugin/DB/cache/hosting choices document speed/reliability/cost/simplicity/security trade-offs. | Review applicable ADR. | WordPress ADR, alternatives and approval note. |
| FS-072 | Recovery steps restore DB, uploads, theme, plugin, config and cache clearly enough for another operator. | Follow restore runbook in staging/test environment. | Restore runbook, drill evidence, owner list. |
| FS-073 | Each production plugin module/theme area/admin workflow/alert/support process has accountable ownership. | Verify who handles failure/escalation. | Ownership matrix, support workflow, alert recipients. |
| FS-074 | Because native MySQL RLS is normally unavailable, plugin code enforces owner, tenant/organisation, role, status, capability and `WHERE`-scoped access at every private entry point. | User A attempts read/edit/delete/export/inference of User B through URL, REST, AJAX, admin and direct IDs. | Row-scoped query proof, permission tests, denied-access logs. |
| FS-075 | Security closure covers nonce, `current_user_can`, `map_meta_cap`, sanitization, escaping, prepared SQL, REST `permission_callback`, CORS, headers, secrets, rate limits, audit logs and dependency checks. | Run WordPress security checklist, headers/dependencies, permission and abuse tests. | Security checklist, scan reports, threat model, approval evidence. |

## Coverage and authority

This overlay must contain every `FS-001` through `FS-075` exactly once. Missing/duplicate IDs are a validation failure. Applicability is still decided per project/task; a non-applicable control requires a specific reason rather than a blank row.
