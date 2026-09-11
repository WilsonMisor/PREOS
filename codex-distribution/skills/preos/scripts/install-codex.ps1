$ErrorActionPreference = 'Stop'
$Root = Resolve-Path (Join-Path $PSScriptRoot '..')
$CodexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME '.codex' }
$AgentsHome = if ($env:AGENTS_HOME) { $env:AGENTS_HOME } else { Join-Path $HOME '.agents' }
$SkillRoot = if ($env:CODEX_SKILLS_HOME) { $env:CODEX_SKILLS_HOME } else { Join-Path $AgentsHome 'skills' }
$Dist = Join-Path $Root 'codex-distribution'
if (-not (Test-Path (Join-Path $Dist 'skills'))) {
    & python (Join-Path $Root 'scripts\build_codex_distribution.py')
}
New-Item -ItemType Directory -Force -Path $SkillRoot | Out-Null
$BackupRoot = Join-Path $CodexHome ('framework-install-backups\preos-' + (Get-Date -Format 'yyyyMMddTHHmmssZ'))
function Backup-ExistingPath([string]$Path) {
    if (Test-Path $Path) {
        New-Item -ItemType Directory -Force -Path $BackupRoot | Out-Null
        $Name = Split-Path $Path -Leaf
        Move-Item -LiteralPath $Path -Destination (Join-Path $BackupRoot $Name)
    }
}
$Skills = @('preos','preos-project-init','preos-risk-model','preos-architecture-economics','preos-production-plan','preos-production-implement','preos-production-learn')
foreach ($Skill in $Skills) {
    $Source = Join-Path $Dist ('skills\' + $Skill)
    if (-not (Test-Path (Join-Path $Source 'SKILL.md'))) { throw ('PREOS distribution missing skill: ' + $Skill) }
    $Target = Join-Path $SkillRoot $Skill
    Backup-ExistingPath $Target
    Copy-Item -Recurse -Force $Source $Target
    if (-not (Test-Path (Join-Path $Target 'SKILL.md'))) { throw ('Installed PREOS skill missing SKILL.md: ' + $Skill) }
}
$Commit = (& git -C $Root rev-parse --short HEAD).Trim()
Write-Output ('Installed PREOS skills under ' + $SkillRoot)
Write-Output ('PREOS commit ' + $Commit)
if (Test-Path $BackupRoot) { Write-Output ('Previous PREOS targets backed up under ' + $BackupRoot) }
Write-Output 'Install gstack with its supported Codex namespaced setup: setup --host codex --prefix.'
