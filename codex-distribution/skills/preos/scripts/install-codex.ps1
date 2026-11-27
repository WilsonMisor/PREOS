$ErrorActionPreference = 'Stop'
$Root = Resolve-Path (Join-Path $PSScriptRoot '..')
$CodexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME '.codex' }
$SkillRoot = if ($env:CODEX_SKILL_ROOT) { $env:CODEX_SKILL_ROOT } elseif ($env:CODEX_SKILLS_HOME) { $env:CODEX_SKILLS_HOME } else { Join-Path $CodexHome 'skills' }
$Dist = Join-Path $Root 'codex-distribution'
if (-not (Test-Path (Join-Path $Dist 'skills'))) {
    & python (Join-Path $Root 'scripts\build_codex_distribution.py')
}
$Manifest = Get-Content -LiteralPath (Join-Path $Root 'CODEX-DISTRIBUTION.json') -Raw | ConvertFrom-Json
$Skills = @($Manifest.skills | ForEach-Object { [string]$_.name })
if (-not $Skills -or $Skills.Count -eq 0) { throw 'PREOS manifest did not declare skills' }
New-Item -ItemType Directory -Force -Path $SkillRoot | Out-Null
$BackupRoot = Join-Path $CodexHome ('framework-install-backups\preos-' + (Get-Date -Format 'yyyyMMddTHHmmssZ'))
function Backup-ExistingPath([string]$Path) {
    if (Test-Path $Path) {
        $ResolvedTarget = [System.IO.Path]::GetFullPath($Path)
        $Prefix = [System.IO.Path]::GetFullPath($SkillRoot).TrimEnd('\','/') + [System.IO.Path]::DirectorySeparatorChar
        if (-not $ResolvedTarget.StartsWith($Prefix, [System.StringComparison]::OrdinalIgnoreCase)) { throw 'Backup target escapes PREOS skill root' }
        New-Item -ItemType Directory -Force -Path $BackupRoot | Out-Null
        $Name = Split-Path $Path -Leaf
        Move-Item -LiteralPath $Path -Destination (Join-Path $BackupRoot $Name)
    }
}
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
