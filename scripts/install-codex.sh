#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${CODEX_HOME:-$HOME/.codex}/skills"
mkdir -p "$DEST"
for skill in preos preos-project-init preos-risk-model preos-architecture-economics preos-production-plan preos-production-implement preos-production-learn; do
  src="$ROOT"
  [[ "$skill" != "preos" ]] && src="$ROOT/$skill"
  rm -rf "$DEST/$skill"
  cp -R "$src" "$DEST/$skill"
done
printf 'Installed PREOS skills under %s\n' "$DEST"
printf 'Install gstack separately using its supported Codex namespaced setup.\n'
