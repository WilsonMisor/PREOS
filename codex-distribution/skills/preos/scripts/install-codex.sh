#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
SKILL_ROOT="${CODEX_SKILL_ROOT:-${CODEX_SKILLS_HOME:-$CODEX_HOME/skills}}"
DIST="$ROOT/codex-distribution"
if [ ! -d "$DIST/skills" ]; then
  python "$ROOT/scripts/build_codex_distribution.py"
fi
mapfile -t SKILLS < <(python - "$ROOT/CODEX-DISTRIBUTION.json" <<'PY' | tr -d '\r'
import json, pathlib, sys
manifest = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding='utf-8'))
for skill in manifest.get('skills', []):
    name = skill.get('name')
    if not name:
        raise SystemExit('PREOS CODEX-DISTRIBUTION.json contains an unnamed skill')
    print(name)
PY
)
[ "${#SKILLS[@]}" -gt 0 ] || { echo 'PREOS manifest did not declare skills' >&2; exit 2; }
mkdir -p "$SKILL_ROOT"
BACKUP_ROOT="$CODEX_HOME/framework-install-backups/preos-$(date -u +%Y%m%dT%H%M%SZ)"
backup_existing_path() {
  target="$1"
  if [ -e "$target" ]; then
    mkdir -p "$BACKUP_ROOT"
    mv "$target" "$BACKUP_ROOT/$(basename "$target")"
  fi
}
for skill in "${SKILLS[@]}"; do
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