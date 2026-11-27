# gstack Integration

PREOS determines which assurance question must be answered. gstack supplies the specialist who attacks or verifies it.

| PREOS need | Namespaced gstack route |
|---|---|
| Product premise or discovery challenge | `gstack-office-hours` |
| Product value/scope challenge | `gstack-plan-ceo-review` |
| Architecture, failure modes, data flow, test plan | `gstack-plan-eng-review` |
| Planned design quality | `gstack-plan-design-review` |
| Security/threat review | `gstack-cso` |
| Code review | `gstack-review` |
| Root-cause investigation | `gstack-investigate` |
| Browser QA with fixes authorised | `gstack-qa` |
| Report-only QA | `gstack-qa-only` |
| Performance/capacity evidence | `gstack-benchmark` |
| Release preparation | `gstack-ship` |
| Explicitly approved production deployment | `gstack-land-and-deploy` |
| Canary validation | `gstack-canary` |
| Post-release reflection | `gstack-retro` |

When PREOS routes a specialist, provide requirement IDs, risk IDs, control IDs, relevant ADRs, evidence requirements, current gate state, task/review scope and known exceptions. gstack may challenge but cannot silently alter Blueprint-approved baselines or accept PREOS risk.
