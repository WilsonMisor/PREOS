# Virtual Team Ownership Matrix

Every applicable domain requires a real accountable human role. If the project lacks that role, the Context Engine must create a ROLE GAP rather than assigning authority to the AI agent.

| Domain | Accountable | Implementation | Review / Approval | Escalation | Default role-gap rule |
|---|---|---|---|---|---|
| Product and Business Rules | PDM,PO | BA,SWE,DEV,PRODENG | STAFF,QA,FIN,LEGAL | SP,PM | Block high-risk acceptance if accountable or required reviewer authority is unstaffed. |
| Data Semantics and Data Types | STAFF,DBA,BA | BE,FS,DATA | QA,DATA,BI | PSA | Block high-risk acceptance if accountable or required reviewer authority is unstaffed. |
| Database Design | DBA,STAFF | DBA,BE,DATA | SRE,QA,SEC | PSA,IC | Block high-risk acceptance if accountable or required reviewer authority is unstaffed. |
| Frontend Engineering | FE,UX-D | FE,WEB,FS | QA,AUTO,ACC,APPSEC,LOC | STAFF,PDM | Block high-risk acceptance if accountable or required reviewer authority is unstaffed. |
| Mobile Engineering | MOB | MOB | QA,AUTO,SEC,PRIVENG,ACC | STAFF,PDM | Block high-risk acceptance if accountable or required reviewer authority is unstaffed. |
| API Engineering | STAFF,BE | BE,FS,WEB | APPSEC,QA,AUTO,SRE | PSA,SEC | Block high-risk acceptance if accountable or required reviewer authority is unstaffed. |
| Authentication | ID,SEC | ID,BE | APPSEC,QA,PRIVENG | SEC,IC | Block high-risk acceptance if accountable or required reviewer authority is unstaffed. |
| Authorization and Tenant Isolation | APPSEC,ID | BE,DBA,FS | SEC,QA,AUTO,PRIVENG | SEC,SP | Block high-risk acceptance if accountable or required reviewer authority is unstaffed. |
| Verification, Trust, and Reputation | TSAFE,PDM | TSAFE,BE,AI | SEC,COMP,PRIVENG,LEGAL,QA | SP,LEGAL | Block high-risk acceptance if accountable or required reviewer authority is unstaffed. |
| Trade Assurance and Protected Transactions | PDM,PAY,TSAFE | PAY,BE,DBA | FIN,COMP,LEGAL,SEC,QA | SP,LEGAL,FIN | Block high-risk acceptance if accountable or required reviewer authority is unstaffed. |
| Money and Financial Correctness | PAY,FIN | PAY,BE,DBA | FIN,COMP,APPSEC,QA,LEGAL | SP,FIN,LEGAL | Block high-risk acceptance if accountable or required reviewer authority is unstaffed. |
| Billing and Subscription | PDM,REVOPS,FIN | PAY,BE,CRM | QA,FIN,LEGAL,CX | SP,FIN | Block high-risk acceptance if accountable or required reviewer authority is unstaffed. |
| Files and Object Storage | CLOUD,SEC | BE,CLOUD,DEVOPS | APPSEC,PRIVENG,QA,FINOPS | SEC,SRE | Block high-risk acceptance if accountable or required reviewer authority is unstaffed. |
| Queues, Events, and Background Work | STAFF,SRE | BE,DEVOPS | QA,AUTO,DBA,FINOPS | SRE,IC | Block high-risk acceptance if accountable or required reviewer authority is unstaffed. |
| Caching | STAFF,SRE | BE,DEVOPS | QA,APPSEC,PERF,DBA | SRE | Block high-risk acceptance if accountable or required reviewer authority is unstaffed. |
| Search | DATA,BE | BE,DATA | APPSEC,QA,PERF,FINOPS | STAFF,SRE | Block high-risk acceptance if accountable or required reviewer authority is unstaffed. |
| Notifications | PDM,CX | BE,MOB,EMAIL,CRM | QA,PRIVENG,LEGAL,LOC,FINOPS | PDM,OPS | Block high-risk acceptance if accountable or required reviewer authority is unstaffed. |
| Networking | CLOUD,SRE | DEVOPS,CLOUD | SEC,PERF,QA | SRE,IC | Block high-risk acceptance if accountable or required reviewer authority is unstaffed. |
| Cloud and Compute | CLOUD,SRE | DEVOPS,CLOUD | FINOPS,SEC,PERF | PSA,IC | Block high-risk acceptance if accountable or required reviewer authority is unstaffed. |
| Scaling and Capacity | SRE,PERF | SRE,DEVOPS,BE,DBA | STAFF,FINOPS,CX | PSA,IC | Block high-risk acceptance if accountable or required reviewer authority is unstaffed. |
| Adaptive Complexity | PSA,STAFF | STAFF,CLOUD,DEVOPS,DBA | SRE,FINOPS,PDM | SP,PSA | Block high-risk acceptance if accountable or required reviewer authority is unstaffed. |
| Cost and FinOps | FINOPS,FIN | FINOPS,DEVOPS,OPS | PSA,PDM,SRE,REVOPS | SP,FIN | Block high-risk acceptance if accountable or required reviewer authority is unstaffed. |
| Security | SEC,APPSEC | APPSEC,BE,FE,DEVOPS | SEC,QA,AUTO,PRIVENG | SEC,IC,SP | Block high-risk acceptance if accountable or required reviewer authority is unstaffed. |
| Privacy and Data Lifecycle | PRIVENG,DPO,PRIV | PRIVENG,BE,DATA,DEVOPS | LEGAL,COMP,SEC | DPO,LEGAL,SP | Block high-risk acceptance if accountable or required reviewer authority is unstaffed. |
| CI, CD, and Version Control | DEVOPS,STAFF | DEVOPS,SWE,AUTO | QA,SEC,SRE | STAFF,IC | Block high-risk acceptance if accountable or required reviewer authority is unstaffed. |
| Observability | SRE | SRE,DEVOPS,BE,DATA | SEC,PRIVENG,FINOPS,QA | IC,OPSTRAT | Block high-risk acceptance if accountable or required reviewer authority is unstaffed. |
| Reliability and Availability | SRE,PSA | SRE,DEVOPS,BE | PERF,QA,CLOUD | IC,SP | Block high-risk acceptance if accountable or required reviewer authority is unstaffed. |
| Backup, Recovery, and Disaster Recovery | SRE,DBA | SRE,DEVOPS,DBA,CLOUD | SEC,QA,OPS,CX | IC,SP | Block high-risk acceptance if accountable or required reviewer authority is unstaffed. |
| Human Error and Insider Risk | OPSTRAT,OPS,SEC | OPS,DEVOPS,HR,SUPENG | COMP,FIN,QA,STAFF | IC,SP | Block high-risk acceptance if accountable or required reviewer authority is unstaffed. |
| Support and Operations | CX,OPS | SUPENG,OPS,BE | SEC,QA,PDM,FIN | OPSTRAT,IC | Block high-risk acceptance if accountable or required reviewer authority is unstaffed. |
| Legal, Contractual, and Evidence Exposure | LEGAL,COMP | PDM,BA,TW,BE,PRIVENG | LEGAL,DPO,FIN,ACC | SP,LEGAL | Block high-risk acceptance if accountable or required reviewer authority is unstaffed. |
| AI Specific Risks | AI,SEC | AI,BE,DATA | APPSEC,PRIVENG,TSAFE,LEGAL,QA,FINOPS | SEC,SP | Block high-risk acceptance if accountable or required reviewer authority is unstaffed. |
| Configuration and Feature-State Engineering | STAFF,DEVOPS | DEVOPS,BE,FE | QA,SRE,SEC | STAFF,IC | Block high-risk acceptance if accountable or required reviewer authority is unstaffed. |
| Software Supply Chain and Build Provenance | APPSEC,DEVOPS | DEVOPS,SWE | SEC,STAFF,COMP | SEC,IC | Block high-risk acceptance if accountable or required reviewer authority is unstaffed. |
| Feature Lifecycle and Product Debt | PDM,PO | SWE,DEV,STAFF | PM,SRE,FINOPS,CX | PDM,SP | Block high-risk acceptance if accountable or required reviewer authority is unstaffed. |
| Change Impact Engineering | STAFF,PM | SWE,DEV,DEVOPS | QA,SRE,APPSEC,PDM | PSA,IC | Block high-risk acceptance if accountable or required reviewer authority is unstaffed. |
| Compatibility and Version Evolution | STAFF,SA | BE,MOB,FE,DATA | QA,AUTO,PDM,TW | PSA,PDM | Block high-risk acceptance if accountable or required reviewer authority is unstaffed. |
| Time and Temporal Correctness | STAFF,DBA | BE,DBA,MOB | QA,AUTO,PAY | STAFF | Block high-risk acceptance if accountable or required reviewer authority is unstaffed. |
| Data Lineage and Provenance | DATA,DBA | DATA,BE,BI | COMP,FIN,QA,PRIVENG | STAFF | Block high-risk acceptance if accountable or required reviewer authority is unstaffed. |
| Data Quality Engineering | DATA,DBA | DATA,BE | BI,QA,BA | STAFF,PDM | Block high-risk acceptance if accountable or required reviewer authority is unstaffed. |
| Decision Automation Risk | PDM,TSAFE | BE,AI,DATA | LEGAL,COMP,QA,PRIVENG | SP,PDM | Block high-risk acceptance if accountable or required reviewer authority is unstaffed. |
| Economic Abuse Surface | FINOPS,TSAFE,SEC | BE,DEVOPS,TSAFE | FIN,APPSEC,PDM | FIN,SEC,IC | Block high-risk acceptance if accountable or required reviewer authority is unstaffed. |
| Organizational Knowledge and Bus-Factor Risk | OPSTRAT,HR | TW,OPS,STAFF | SP,PM,SRE | SP | Block high-risk acceptance if accountable or required reviewer authority is unstaffed. |
| Vendor Viability and Concentration Risk | VENDOR,FIN | VENDOR,CLOUD,BE | LEGAL,FINOPS,SRE,SEC | SP,FIN | Block high-risk acceptance if accountable or required reviewer authority is unstaffed. |
| Critical Account and Domain Ownership | OPS,SEC,FIN | OPS,DEVOPS,VENDOR | COMP,LEGAL,SRE | SP,SEC | Block high-risk acceptance if accountable or required reviewer authority is unstaffed. |
| Multidimensional Capacity Vectors | SRE,PERF,FINOPS | SRE,DATA,DEVOPS | STAFF,PDM,FIN | PSA,SP | Block high-risk acceptance if accountable or required reviewer authority is unstaffed. |
| Evidence Freshness and Validity | QA,AUTO,COMP | AUTO,QA,DEVOPS | STAFF,SEC,SRE | OPSTRAT | Block high-risk acceptance if accountable or required reviewer authority is unstaffed. |
| Control Dependency Graph | STAFF,QA | STAFF,AUTO | SEC,SRE,PSA | OPSTRAT | Block high-risk acceptance if accountable or required reviewer authority is unstaffed. |
| Risk Aggregation and Release Risk | OPSTRAT,PDM | OPSTRAT,PM,QA | SEC,SRE,FIN,SP | SP | Block high-risk acceptance if accountable or required reviewer authority is unstaffed. |
| Risk Acceptance Lifecycle | SP,OPSTRAT | OPSTRAT,COMP | SEC,LEGAL,FIN,PDM | SP | Block high-risk acceptance if accountable or required reviewer authority is unstaffed. |
| Human Authority and Decision Rights | SP,OPSTRAT | OPSTRAT,PM | LEGAL,COMP,SEC,FIN | SP | Block high-risk acceptance if accountable or required reviewer authority is unstaffed. |
| AI Coding Agent Authority Boundary | STAFF,SEC,PDM | AI,STAFF | APPSEC,QA,OPSTRAT | SP,SEC | Block high-risk acceptance if accountable or required reviewer authority is unstaffed. |
