# Installation

PREOS is installed beside the AI Product Delivery Blueprint and namespaced gstack skills.

## Codex skill layout

Expected conceptual layout:

```text
~/.codex/skills/
  ai-product-delivery-blueprint/
  preos/
  preos-project-init/
  preos-risk-model/
  preos-architecture-economics/
  preos-production-plan/
  preos-production-implement/
  preos-production-learn/
  gstack-*/
```

Run `scripts/install-codex.ps1` on Windows or `scripts/install-codex.sh` on Unix-like systems after cloning PREOS. gstack should be installed independently with its supported `--host codex --prefix` workflow.

Installation does not authorize production changes or risk acceptance.
