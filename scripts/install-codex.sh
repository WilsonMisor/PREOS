#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
AGENTS_HOME="${AGENTS_HOME:-$HOME/.agents}"
SKILL_ROOT="${CODEX_SKILLS_HOME:-$AGENTS_HOME/skills}"
DIST="$ROOT/codex-distribution"
if [ ! -d "$DIST/skills" ]; then
  python "$ROOT/scripts/build_codex_distribution.py"
fi
mkdir -p "$SKILL_ROOT"
BACKUP_ROOT="$CODEX_HOME/framework-install-backups/preos-$(date -u +%Y%m%dT%H%M%SZ)"
backup_existing_path() {
  target="$1"
  if [ -e "$target" ]; then
    mkdir -p "$BACKUP_ROOT"
    mv "$target" "$BACKUP_ROOT/$(basename "$target")"
  fi
}
for skill in preos preos-project-init preos-risk-model preos-architecture-economics preos-production-plan preos-production-implement preos-production-learn; do
  source="$DIST/skills/$skill"
  [ -f "$source/SKILL.md" ] || { echo "PREOS distribution missing skill: $skill" >&2; exit 2; }
  target="$SKILL_ROOT/$skill"
  backup_existing_path "$target"
  cp -R "$source" "$target"
  [ -f "$target/SKILL.md" ] || { echo "Installed PREOS skill missing SKILL.md: $skill" >&2; exit 3; }
done
commit=$(git -C "$ROOT" rev-parse --short HEAD)
printf 'Installed PREOS skills under %s\n' "$SKILL_ROOT"
printf 'PREOS commit %s\n' "$commit"
[ -d "$BACKUP_ROOT" ] && printf 'Previous PREOS targets backed up under %s\n' "$BACKUP_ROOT"
printf 'Install gstack with its supported Codex namespaced setup: setup --host codex --prefix.\n'
