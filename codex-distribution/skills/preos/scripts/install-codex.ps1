$ErrorActionPreference = 'Stop'
$Root = Resolve-Path (Join-Path $PSScriptRoot '..')
$CodexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME '.codex' }
$Dest = Join-Path $CodexHome 'skills'
New-Item -ItemType Directory -Force -Path $Dest | Out-Null
$Skills = @('preos','preos-project-init','preos-risk-model','preos-architecture-economics','preos-production-plan','preos-production-implement','preos-production-learn')
foreach ($Skill in $Skills) {
    $Source = if ($Skill -eq 'preos') { $Root } else { Join-Path $Root $Skill }
    $Target = Join-Path $Dest $Skill
    if (Test-Path $Target) { Remove-Item -Recurse -Force $Target }
    Copy-Item -Recurse -Force $Source $Target
}
Write-Output "Installed PREOS skills under $Dest"
Write-Output 'Install gstack separately using its supported Codex namespaced setup.'
