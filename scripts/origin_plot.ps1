[CmdletBinding()]
param(
    [string]$Csv,
    [string]$X,
    [string]$Y,
    [string]$Title,
    [string]$XLabel,
    [string]$YLabel,
    [string]$OutDir = '.\origin_output',
    [string]$Name = 'origin_plot',
    [string]$OriginExe,
    [switch]$Fit,
    [switch]$Pdf,
    [switch]$NoExport,
    [switch]$DryRun,
    [switch]$DetectOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$inv = [System.Globalization.CultureInfo]::InvariantCulture

function Assert-Ascii([string]$Value, [string]$What) {
    if ($Value -match '[^\x20-\x7E]') {
        throw "$What must be ASCII. Origin mangles non-ASCII LabTalk text."
    }
    if ($Value -match '["\\]') {
        throw "$What cannot contain a double quote or backslash."
    }
}

function Format-Num([double]$Value) {
    return $Value.ToString('R', $inv)
}

function Find-OriginExecutable([string]$Override) {
    if ($Override) {
        $resolved = [System.IO.Path]::GetFullPath($Override)
        if (-not (Test-Path -LiteralPath $resolved -PathType Leaf)) {
            throw "Origin executable not found: $resolved"
        }
        return $resolved
    }

    $candidates = New-Object System.Collections.Generic.List[string]
    $uninstallRoots = @(
        'Registry::HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall',
        'Registry::HKEY_LOCAL_MACHINE\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall',
        'Registry::HKEY_CURRENT_USER\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall'
    )
    foreach ($root in $uninstallRoots) {
        if (-not (Test-Path $root)) { continue }
        foreach ($key in @(Get-ChildItem $root -ErrorAction SilentlyContinue)) {
            $app = Get-ItemProperty $key.PSPath -ErrorAction SilentlyContinue
            if (-not $app -or -not $app.PSObject.Properties['DisplayName']) { continue }
            if ([string]$app.DisplayName -notmatch '^Origin') { continue }

            $icon = if ($app.PSObject.Properties['DisplayIcon']) { [string]$app.DisplayIcon } else { '' }
            if ($icon -match '^\s*"([^"]+\.exe)"') {
                $candidates.Add($Matches[1])
            }
            elseif ($icon -match '^\s*([^\s,]+\.exe)') {
                $candidates.Add($Matches[1])
            }

            if ($app.PSObject.Properties['InstallLocation'] -and $app.InstallLocation) {
                $candidates.Add((Join-Path ([string]$app.InstallLocation) 'Origin64.exe'))
            }
        }
    }

    $programRoots = @($env:ProgramFiles, ${env:ProgramFiles(x86)}, $env:ProgramW6432) |
        Where-Object { $_ -and (Test-Path -LiteralPath $_) } |
        Select-Object -Unique
    foreach ($root in $programRoots) {
        $originRoot = Join-Path $root 'OriginLab'
        if (-not (Test-Path -LiteralPath $originRoot)) { continue }
        foreach ($dir in @(Get-ChildItem -LiteralPath $originRoot -Directory -ErrorAction SilentlyContinue)) {
            $candidates.Add((Join-Path $dir.FullName 'Origin64.exe'))
        }
    }

    $command = Get-Command 'Origin64.exe' -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($command) { $candidates.Add($command.Source) }

    $found = New-Object System.Collections.Generic.List[object]
    foreach ($candidate in @($candidates | Select-Object -Unique)) {
        if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) { continue }
        $file = Get-Item -LiteralPath $candidate
        $version = $null
        try { $version = [version]$file.VersionInfo.ProductVersion } catch {}
        $found.Add([pscustomobject]@{
            Path = $file.FullName
            Version = $(if ($version) { $version } else { [version]'0.0' })
        })
    }

    $best = $found | Sort-Object -Property @{ Expression = 'Version'; Descending = $true },
        @{ Expression = 'Path'; Descending = $false } | Select-Object -First 1
    if ($best) { return $best.Path }
    return $null
}

function Get-OriginUserStatus {
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $identityUser = ($identity.Name -split '\\')[-1]
    $profileUser = Split-Path -Leaf $env:USERPROFILE
    $matchesDesktopUser = $identityUser -ieq $profileUser
    $isInteractive = [Environment]::UserInteractive -and ([System.Diagnostics.Process]::GetCurrentProcess().SessionId -ne 0)
    return [pscustomobject]@{
        Identity = $identity.Name
        UserProfile = $env:USERPROFILE
        IsInteractive = $isInteractive
        MatchesDesktopUser = $matchesDesktopUser
        CanUseCom = $isInteractive -and $matchesDesktopUser
    }
}

function Register-OriginCom([string]$Executable) {
    $definitions = @(
        @{ ProgId = 'Origin.Application'; Clsid = '{B0F21977-8AAB-4632-A73D-528B909C5663}' },
        @{ ProgId = 'Origin.ApplicationSI'; Clsid = '{2F234A01-A4EB-4EAB-A130-A13C97953F0B}' },
        @{ ProgId = 'Origin.ApplicationCOMSI'; Clsid = '{9FE89513-7A1C-4229-8DF1-AB272A668E52}' }
    )
    $classes = 'HKCU:\Software\Classes'
    foreach ($definition in $definitions) {
        $progId = Join-Path $classes $definition.ProgId
        New-Item -Path $progId -Force | Out-Null
        Set-Item -Path $progId -Value 'Origin Automation Server'
        New-Item -Path (Join-Path $progId 'CLSID') -Force | Out-Null
        Set-Item -Path (Join-Path $progId 'CLSID') -Value $definition.Clsid

        $clsid = Join-Path (Join-Path $classes 'CLSID') $definition.Clsid
        New-Item -Path $clsid -Force | Out-Null
        Set-Item -Path $clsid -Value $definition.ProgId
        $server = Join-Path $clsid 'LocalServer32'
        New-Item -Path $server -Force | Out-Null
        Set-Item -Path $server -Value ('"' + $Executable + '"')
    }
}

function Test-OriginComRegistration([string]$Executable) {
    $progId = 'Registry::HKEY_CLASSES_ROOT\Origin.ApplicationSI\CLSID'
    if (-not (Test-Path $progId)) { return $false }
    $clsid = (Get-ItemProperty $progId -ErrorAction SilentlyContinue).'(default)'
    if (-not $clsid) { return $false }
    $server = "Registry::HKEY_CLASSES_ROOT\CLSID\$clsid\LocalServer32"
    if (-not (Test-Path $server)) { return $false }
    $registered = [string](Get-ItemProperty $server -ErrorAction SilentlyContinue).'(default)'
    if (-not $registered) { return $false }
    $registered = $registered.Trim().Trim('"')
    return [string]::Equals(
        [System.IO.Path]::GetFullPath($registered),
        [System.IO.Path]::GetFullPath($Executable),
        [System.StringComparison]::OrdinalIgnoreCase)
}

function New-OriginCom([string]$Executable) {
    try {
        return New-Object -ComObject Origin.ApplicationSI
    }
    catch {
        $hresult = $_.Exception.HResult
        $classMissing = $hresult -eq [int]0x80040154
        $serverMissing = $hresult -eq [int]0x80070002
        if (-not ($classMissing -or $serverMissing)) { throw }
        Register-OriginCom $Executable
        return New-Object -ComObject Origin.ApplicationSI
    }
}

function Test-DemoWatermark([string]$Path) {
    Add-Type -AssemblyName System.Drawing
    $bmp = [System.Drawing.Bitmap]::FromFile($Path)
    try {
        $step = [Math]::Max(1, [int]($bmp.Width / 500))
        $cells = New-Object 'int[,]' 4, 4
        for ($y = 0; $y -lt $bmp.Height; $y += $step) {
            for ($x = 0; $x -lt $bmp.Width; $x += $step) {
                $c = $bmp.GetPixel($x, $y)
                if ($c.R -lt 80 -and $c.G -gt 200 -and $c.B -gt 200) {
                    $cx = [Math]::Min(3, [int]($x * 4 / $bmp.Width))
                    $cy = [Math]::Min(3, [int]($y * 4 / $bmp.Height))
                    $cells[$cx, $cy] = $cells[$cx, $cy] + 1
                }
            }
        }
        $hit = 0
        for ($i = 0; $i -lt 4; $i++) {
            for ($j = 0; $j -lt 4; $j++) {
                if ($cells[$i, $j] -gt 5) { $hit++ }
            }
        }
        return ($hit -ge 6)
    }
    finally {
        $bmp.Dispose()
    }
}

$origin = $null
$tempBase = $null
try {
    $originExecutable = $null
    $originUser = $null
    if (-not $DryRun) {
        $originExecutable = Find-OriginExecutable $OriginExe
        $originUser = Get-OriginUserStatus
        if ($DetectOnly) {
            Write-Output "Origin: $(if ($originExecutable) { $originExecutable } else { 'not found' })"
            Write-Output "User: $($originUser.Identity)"
            Write-Output "Desktop context: $($originUser.CanUseCom)"
            if ($originExecutable) {
                Write-Output "COM ready from this process: $($originUser.CanUseCom)"
                if (-not $originUser.CanUseCom) {
                    Write-Output 'Fix: rerun from an interactive terminal owned by the desktop user.'
                }
            }
            else {
                Write-Output 'Fix: install Origin, put Origin64.exe on PATH, or pass -OriginExe.'
                exit 1
            }
            return
        }
        if (-not $originExecutable) {
            throw 'ORIGIN_NOT_FOUND: Origin64.exe was not found. Pass -OriginExe with the installed executable path.'
        }
        if (-not $originUser.CanUseCom) {
            throw "SANDBOX: Origin COM requires the interactive desktop user. Current identity is '$($originUser.Identity)' but the desktop profile is '$($originUser.UserProfile)'. Rerun the command in a desktop-user terminal; Origin was found at '$originExecutable'."
        }
        if ($OriginExe -and -not (Test-OriginComRegistration $originExecutable)) {
            Register-OriginCom $originExecutable
        }
    }

    if (-not $DryRun -and (Get-Process -Name Origin64 -ErrorAction SilentlyContinue)) {
        throw 'Origin is already running. Close it first; this script starts and closes its own instance.'
    }
    if (-not $Csv -or -not $X -or -not $Y) {
        throw 'Csv, X and Y are required unless -DetectOnly is used.'
    }
    if (-not (Test-Path -LiteralPath $Csv)) {
        throw "CSV not found: $Csv"
    }

    Assert-Ascii $Name 'Name'
    if ($Title) { Assert-Ascii $Title 'Title' }
    if ($XLabel) { Assert-Ascii $XLabel 'XLabel' }
    if ($YLabel) { Assert-Ascii $YLabel 'YLabel' }

    $rows = @(Import-Csv -LiteralPath $Csv -Encoding UTF8)
    if ($rows.Count -lt 2) { throw 'CSV needs a header and at least one data row.' }
    $columns = @($rows[0].PSObject.Properties.Name)
    if ($columns -notcontains $X) { throw "Column '$X' not found. Available: $($columns -join ', ')" }
    if ($columns -notcontains $Y) { throw "Column '$Y' not found. Available: $($columns -join ', ')" }

    $data = New-Object System.Collections.Generic.List[object]
    $rowNo = 1
    foreach ($row in $rows) {
        $rowNo++
        $dx = [double]0
        $dy = [double]0
        $sx = [string]$row.$X
        $sy = [string]$row.$Y
        if (-not [double]::TryParse($sx, [System.Globalization.NumberStyles]::Float, $inv, [ref]$dx) -or
            -not [double]::TryParse($sy, [System.Globalization.NumberStyles]::Float, $inv, [ref]$dy)) {
            throw "Row $rowNo has a non-numeric '$X' or '$Y' value."
        }
        [void]$data.Add([pscustomobject]@{ X = $dx; Y = $dy })
    }
    if ($data.Count -gt 2000) { throw 'This script supports up to 2000 data points.' }
    $sorted = @($data | Sort-Object -Property X)

    $slope = $null
    $intercept = $null
    $r2 = $null
    if ($Fit) {
        if ($sorted.Count -lt 3) { throw 'Linear fit needs at least 3 points.' }
        $n = [double]$sorted.Count
        $sx = [double]0; $sy = [double]0; $sxx = [double]0; $sxy = [double]0
        foreach ($p in $sorted) {
            $sx += $p.X; $sy += $p.Y
            $sxx += $p.X * $p.X; $sxy += $p.X * $p.Y
        }
        $den = $n * $sxx - $sx * $sx
        if ([Math]::Abs($den) -lt 1e-300) { throw 'Cannot fit: all X values are equal.' }
        $slope = ($n * $sxy - $sx * $sy) / $den
        $intercept = ($sy - $slope * $sx) / $n
        $my = $sy / $n
        $sse = [double]0; $sst = [double]0
        foreach ($p in $sorted) {
            $yh = $slope * $p.X + $intercept
            $sse += ($p.Y - $yh) * ($p.Y - $yh)
            $sst += ($p.Y - $my) * ($p.Y - $my)
        }
        $r2 = if ($sst -gt 0) { 1 - $sse / $sst } else { 1 }
    }

    $xLabel = if ($XLabel) { $XLabel } else { $X }
    $yLabel = if ($YLabel) { $YLabel } else { $Y }
    Assert-Ascii $xLabel 'X label'
    Assert-Ascii $yLabel 'Y label'

    $tempBase = Join-Path $env:TEMP ('origin_plot_' + [guid]::NewGuid().ToString('N'))
    if ($tempBase -match '[^\x20-\x7E]') {
        $tempBase = 'C:\Users\Public\origin_plot_' + [guid]::NewGuid().ToString('N')
    }
    New-Item -ItemType Directory -Path $tempBase -Force | Out-Null

    $xValues = ($sorted | ForEach-Object { Format-Num $_.X }) -join ','
    $yValues = ($sorted | ForEach-Object { Format-Num $_.Y }) -join ','

    $sb = New-Object System.Text.StringBuilder
    [void]$sb.AppendLine('doc -n;')
    [void]$sb.AppendLine('newbook name:="PlotData" sheet:=1 option:=lsname;')
    [void]$sb.AppendLine(('wks.ncols={0};' -f $(if ($Fit) { 3 } else { 2 })))
    [void]$sb.AppendLine('col(A)={' + $xValues + '};')
    [void]$sb.AppendLine('col(B)={' + $yValues + '};')
    if ($Fit) {
        $fitValues = ($sorted | ForEach-Object { Format-Num ($slope * $_.X + $intercept) }) -join ','
        [void]$sb.AppendLine('col(C)={' + $fitValues + '};')
    }
    [void]$sb.AppendLine('wks.col1.type=4;')
    [void]$sb.AppendLine('wks.col2.type=1;')
    if ($Fit) { [void]$sb.AppendLine('wks.col3.type=1;') }
    [void]$sb.AppendLine(('wks.col1.lname$="{0}";' -f $xLabel))
    [void]$sb.AppendLine(('wks.col2.lname$="{0}";' -f $yLabel))
    if ($Fit) { [void]$sb.AppendLine('wks.col3.lname$="Linear fit";') }
    [void]$sb.AppendLine('plotxy iy:=(1,2) plot:=201;')
    if ($Fit) {
        [void]$sb.AppendLine('layer -i200 PlotData_C;')
        [void]$sb.AppendLine('legendupdate;')
    }
    [void]$sb.AppendLine('page.zoom=80;')
    if ($Title) {
        [void]$sb.AppendLine(('label -s -sa -d (0.5*page.width) (0.03*page.height) -n title "{0}";' -f $Title))
    }
    if ($Fit) {
        $sign = if ($slope -ge 0) { '+' } else { '-' }
        $eq = 'y = {0} {1} {2} x' -f $intercept.ToString('0.####', $inv), $sign, ([Math]::Abs($slope)).ToString('0.####', $inv)
        $r2Text = 'R2 = {0}' -f $r2.ToString('0.######', $inv)
        [void]$sb.AppendLine(('label -s -sa -d (0.15*page.width) (0.18*page.height) -n eq "{0}";' -f $eq))
        [void]$sb.AppendLine(('label -s -sa -d (0.15*page.width) (0.23*page.height) -n r2 "{0}";' -f $r2Text))
    }

    $ogs = Join-Path $tempBase 'plot.ogs'
    [System.IO.File]::WriteAllText($ogs, $sb.ToString(), (New-Object System.Text.UTF8Encoding($false)))

    if ($DryRun) {
        $outAbs = [System.IO.Path]::GetFullPath($OutDir)
        New-Item -ItemType Directory -Path $outAbs -Force | Out-Null
        Copy-Item -LiteralPath $ogs -Destination (Join-Path $outAbs ($Name + '.ogs')) -Force
        if ($Fit) {
            Write-Output ('Fit: k={0} b={1} R2={2}' -f
                $slope.ToString('0.######', $inv),
                $intercept.ToString('0.######', $inv),
                $r2.ToString('0.######', $inv))
        }
        Write-Output "Dry run: $(Join-Path $outAbs ($Name + '.ogs'))"
        return
    }

    $origin = New-OriginCom $originExecutable
    $origin.Visible = 1
    if (-not $origin.Execute([System.IO.File]::ReadAllText($ogs))) {
        throw 'Origin rejected the generated LabTalk script.'
    }

    $opju = Join-Path $tempBase ($Name + '.opju')
    if (-not $origin.Save($opju) -or -not (Test-Path -LiteralPath $opju)) {
        throw 'Origin did not save the project. Use an ASCII output path.'
    }

    $png = Join-Path $tempBase ($Name + '.png')
    $pdfPath = Join-Path $tempBase ($Name + '.pdf')
    if (-not $NoExport) {
        $ok = $origin.Execute('expGraph type:=png path:="' + $png + '" overwrite:=replace;')
        if (-not $ok -or -not (Test-Path -LiteralPath $png)) {
            throw 'DEMO: Origin export failed. Activate Origin and retry; no formal figure was produced.'
        }
        if (Test-DemoWatermark $png) {
            throw 'DEMO: exported image contains the Origin demo watermark; no formal figure was produced.'
        }
        if ($Pdf) {
            $ok = $origin.Execute('expGraph type:=pdf path:="' + $pdfPath + '" overwrite:=replace;')
            if (-not $ok -or -not (Test-Path -LiteralPath $pdfPath)) {
                throw 'PDF export failed. The Origin project was saved; PNG is still available.'
            }
        }
    }

    $outAbs = [System.IO.Path]::GetFullPath($OutDir)
    New-Item -ItemType Directory -Path $outAbs -Force | Out-Null
    Copy-Item -LiteralPath $opju -Destination (Join-Path $outAbs ($Name + '.opju')) -Force
    if (-not $NoExport) {
        Copy-Item -LiteralPath $png -Destination (Join-Path $outAbs ($Name + '.png')) -Force
        if ($Pdf) {
            Copy-Item -LiteralPath $pdfPath -Destination (Join-Path $outAbs ($Name + '.pdf')) -Force
        }
    }
    Write-Output "Saved: $(Join-Path $outAbs ($Name + '.opju'))"
    if (-not $NoExport) { Write-Output "Saved: $(Join-Path $outAbs ($Name + '.png'))" }
}
catch {
    $message = $_.Exception.Message
    [Console]::Error.WriteLine($message)
    if ($message -like 'DEMO:*') { exit 3 }
    if ($message -like 'SANDBOX:*') { exit 2 }
    exit 1
}
finally {
    if ($origin) { try { $origin.Exit() } catch {} }
    if ($tempBase -and
        ($tempBase.StartsWith([System.IO.Path]::GetTempPath(), [System.StringComparison]::OrdinalIgnoreCase) -or
         $tempBase.StartsWith('C:\Users\Public\origin_plot_', [System.StringComparison]::OrdinalIgnoreCase)) -and
        (Split-Path $tempBase -Leaf) -like 'origin_plot_*') {
        Remove-Item -LiteralPath $tempBase -Recurse -Force -ErrorAction SilentlyContinue
    }
}
