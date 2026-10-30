param([switch]$WithOrigin)

$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
$script = Join-Path $repo 'scripts\origin_plot.ps1'
$csv = Join-Path $repo 'examples\clausius_clapeyron.csv'
$out = Join-Path $PSScriptRoot '_out'
$ps = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'

function Assert($Condition, $Message) {
    if (-not $Condition) { throw "FAIL: $Message" }
    Write-Output "PASS: $Message"
}

if ($out.StartsWith($PSScriptRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    Remove-Item -LiteralPath $out -Recurse -Force -ErrorAction SilentlyContinue
}

& $ps -NoProfile -ExecutionPolicy Bypass -File $script `
    -Csv $csv -X invT_K -Y ln_p_p0 `
    -Title 'Saturated Vapor Pressure of Water' `
    -XLabel '1/T (K^-1)' -YLabel 'ln(p/p0)' `
    -OutDir $out -Name smoke -Fit -DryRun
Assert ($LASTEXITCODE -eq 0) 'dry run exits 0'
$ogsPath = Join-Path $out 'smoke.ogs'
Assert (Test-Path -LiteralPath $ogsPath) 'dry run writes the LabTalk script'
$ogs = Get-Content -Raw -Encoding UTF8 $ogsPath
Assert ($ogs -match 'plotxy iy:=\(1,2\) plot:=201;') 'scatter command is generated'
Assert ($ogs -match 'layer -i200 PlotData_C;') 'fit line is added by dataset name'
Assert ($ogs -match 'page\.zoom=80;') 'page zoom is set'
Assert ($ogs -match '5152\.1094') 'expected fit slope is generated'
Assert ($ogs -match 'R2 = 0\.999') 'fit quality label is generated'

& $ps -NoProfile -ExecutionPolicy Bypass -File $script `
    -Csv $csv -X does_not_exist -Y ln_p_p0 -OutDir $out -Name bad -DryRun
Assert ($LASTEXITCODE -eq 1) 'missing column is rejected'

$detectOutput = @(& $ps -NoProfile -ExecutionPolicy Bypass -File $script -DetectOnly 2>&1 |
    ForEach-Object { [string]$_ })
$detectCode = $LASTEXITCODE
Assert ($detectCode -eq 0 -or $detectCode -eq 1) 'Origin detection exits with a documented status'
Assert (($detectOutput -join "`n") -match '^Origin: ') 'Origin detection reports the executable status'

if ($detectCode -eq 1) {
    Assert (($detectOutput -join "`n") -match 'Origin64\.exe was not found') 'missing Origin has an actionable diagnostic'
}
elseif (($detectOutput -join "`n") -match 'Desktop context: False') {
    & $ps -NoProfile -ExecutionPolicy Bypass -File $script `
        -Csv $csv -X invT_K -Y ln_p_p0 -OutDir $out -Name sandbox_guard
    Assert ($LASTEXITCODE -eq 2) 'sandbox context is rejected before COM activation'
    Assert (-not (Get-Process -Name Origin64 -ErrorAction SilentlyContinue)) 'sandbox guard does not launch Origin'
}

& $ps -NoProfile -ExecutionPolicy Bypass -File $script `
    -DetectOnly -OriginExe (Join-Path $repo 'missing-origin.exe')
Assert ($LASTEXITCODE -eq 1) 'invalid explicit Origin path is rejected'

if (-not $WithOrigin) {
    Write-Output 'SKIP: Origin integration (run with -WithOrigin on a licensed Windows desktop).'
    Write-Output 'ALL CHECKS DONE'
    return
}

if (Get-Process -Name Origin64 -ErrorAction SilentlyContinue) {
    throw 'Close Origin before running the integration test.'
}

& $ps -NoProfile -ExecutionPolicy Bypass -File $script `
    -Csv $csv -X invT_K -Y ln_p_p0 `
    -Title 'Saturated Vapor Pressure of Water' `
    -XLabel '1/T (K^-1)' -YLabel 'ln(p/p0)' `
    -OutDir $out -Name smoke -Fit -NoExport
Assert ($LASTEXITCODE -eq 0) 'project-only run exits 0'
$opju = Join-Path $out 'smoke.opju'
Assert (Test-Path -LiteralPath $opju) 'project file exists'

$origin = New-Object -ComObject Origin.ApplicationSI
try {
    Assert ($origin.Load($opju)) 'saved project reloads'
    Assert ($null -ne $origin.FindWorksheet('PlotData')) 'worksheet is present'
    Assert ($null -ne $origin.FindGraphLayer('Graph1')) 'graph is present'
}
finally {
    try { $origin.Exit() } catch {}
}

& $ps -NoProfile -ExecutionPolicy Bypass -File $script `
    -Csv $csv -X invT_K -Y ln_p_p0 `
    -Title 'Saturated Vapor Pressure of Water' `
    -XLabel '1/T (K^-1)' -YLabel 'ln(p/p0)' `
    -OutDir $out -Name smoke -Fit
$code = $LASTEXITCODE
$png = Join-Path $out 'smoke.png'
if ($code -eq 0) {
    Assert (Test-Path -LiteralPath $png) 'licensed export produced a PNG'
    Assert ((Get-Item -LiteralPath $png).Length -gt 10000) 'PNG is non-trivial'
    Write-Output 'PASS: watermark-free export verified by the plotter'
}
elseif ($code -eq 3) {
    Assert (-not (Test-Path -LiteralPath $png)) 'demo mode produced no formal figure'
    Write-Output 'SKIP: Origin is demo/unlicensed; activate it to test PNG/PDF export.'
}
else {
    throw "FAIL: export run exited $code"
}

Write-Output 'ALL CHECKS DONE'
