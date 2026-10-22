[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [ValidateSet('codex', 'claude', 'all')]
    [string]$Agent = 'all',
    [string]$Source,
    [string]$Destination
)

$ErrorActionPreference = 'Stop'
if (-not $Source) { $Source = Split-Path $PSScriptRoot -Parent }
$skillTargets = @{
    codex  = Join-Path $env:USERPROFILE '.codex\skills\origin-plotting'
    claude = Join-Path $env:USERPROFILE '.claude\skills\origin-plotting'
}

if ($Destination) {
    $targets = @{ custom = $Destination }
}
elseif ($Agent -eq 'all') {
    $targets = $skillTargets
}
else {
    $targets = @{ $Agent = $skillTargets[$Agent] }
}

if (-not (Test-Path -LiteralPath (Join-Path $Source 'SKILL.md'))) {
    throw "Source does not contain SKILL.md: $Source"
}

foreach ($target in $targets.Values) {
    if ($PSCmdlet.ShouldProcess($target, 'Install origin-plotting skill')) {
        New-Item -ItemType Directory -Path $target -Force | Out-Null
        robocopy $Source $target /E /XD .git .mplconfig __pycache__ tests\_out tests\_out_py tests\_out_adv | Out-Null
        if ($LASTEXITCODE -ge 8) {
            throw "Copy failed with robocopy exit code $LASTEXITCODE"
        }
        if (-not (Test-Path -LiteralPath (Join-Path $target 'SKILL.md'))) {
            throw "Install failed: SKILL.md missing in $target"
        }
        Write-Output "Installed: $target"
    }
}

Write-Output 'Restart the agent so it reloads skills.'
Write-Output 'Cursor, Gemini CLI, Copilot, Windsurf and Aider use the adapter files in this repository.'
