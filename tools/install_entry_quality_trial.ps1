# Install and compile the isolated, single-hypothesis entry-quality experiment.
# Installs files only. Never launches MT5, attaches to charts or sends broker orders.
[CmdletBinding()]
param(
    [string]$TerminalPath = '',
    [string]$DataFolder = '',
    [switch]$VerifyOnly
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$researchDir = Join-Path $repo 'research\entry_quality'
$variant = Join-Path $researchDir 'nyao_scalper_entry_gate.mq5'
$preset = Join-Path $researchDir 'Trader_ENTRY_GATE_FIXED001.set'
$original = Join-Path $repo 'nyao_scalper.mq5'
$known = @{
    variant = @('ebda1ba5954d9ea6b0ffcd6f73d734adba13b140cb61bcc28e65e5591c221305','c8dd2450b64bbc53a85fce4504b9915e401f0fe7cfffb14cf8dac840bb16ea39')
    preset = @('a00c60b92009b8f5138bb35e4bb4bf4b27cbb02e23a76ad8f79c9f9500aa2f02','36fb0628671a2a12b352f77029b2617a382260b28a038de0a41bf144f3c05828')
    original = @('91ea11b70553fa413af9712745052fd192039e0627d8f7c3a34e066b80a1c837','f4d5a57075745d8dd41297e3b252b31bbc08996f2eec727c898c2165e3cc9e3b')
}
function Assert-Hash([string]$path, [string]$kind) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw ("Missing " + $kind + ": " + $path) }
    $hash = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($hash -notin $known[$kind]) { throw ("Research source integrity check failed for " + $kind + ": " + $hash) }
    return $hash
}
function Canonical([string]$p) { return ([System.IO.Path]::GetFullPath($p)).TrimEnd('\','/').ToLowerInvariant() }
function Find-Terminal {
    $root = Join-Path $env:APPDATA 'MetaQuotes\Terminal'
    $found = @()
    if (Test-Path -LiteralPath $root -PathType Container) {
        foreach ($dir in @(Get-ChildItem -LiteralPath $root -Directory)) {
            $originFile = Join-Path $dir.FullName 'origin.txt'
            if (-not (Test-Path -LiteralPath $originFile -PathType Leaf)) { continue }
            $line = (Get-Content -LiteralPath $originFile -ErrorAction Stop | Select-Object -First 1)
            if ([string]::IsNullOrWhiteSpace($line)) { continue }
            $path = $line.Trim().Trim('"')
            if ($path -notmatch '(?i)terminal64\.exe$') { $path = Join-Path $path 'terminal64.exe' }
            $editor = Join-Path (Split-Path -Parent $path) 'metaeditor64.exe'
            if ((Test-Path -LiteralPath $path -PathType Leaf) -and (Test-Path -LiteralPath $editor -PathType Leaf)) {
                $found += [pscustomobject]@{ Terminal = $path; Editor = $editor; Data = $dir.FullName }
            }
        }
    }
    if ($DataFolder -ne '') {
        $wantedData = Canonical $DataFolder
        $found = @($found | Where-Object { (Canonical $_.Data) -eq $wantedData })
    }
    if ($TerminalPath -ne '') {
        $wantedTerminal = $TerminalPath
        if (Test-Path -LiteralPath $wantedTerminal -PathType Container) {
            $wantedTerminal = Join-Path $wantedTerminal 'terminal64.exe'
        }
        $wantedTerminal = Canonical $wantedTerminal
        $found = @($found | Where-Object { (Canonical $_.Terminal) -eq $wantedTerminal })
    }
    $found = @($found | Sort-Object Data -Unique)
    if ($found.Count -ne 1) {
        foreach ($item in $found) { Write-Host ('Terminal: ' + $item.Terminal + ' | data: ' + $item.Data) }
        throw 'MT5 installation is missing or ambiguous. Open DEMO MT5 once, or pass -DataFolder and -TerminalPath. No files changed.'
    }
    return $found[0]
}
try {
    Write-Host 'TRADER ENTRY QUALITY EXPERIMENT: INSTALL + COMPILE ONLY.'
    Write-Host 'The original Nyao EA and its original preset are left untouched.'
    $variantHash = Assert-Hash $variant 'variant'
    $presetHash = Assert-Hash $preset 'preset'
    $originalHash = Assert-Hash $original 'original'
    Write-Host ('Verified trial source: ' + $variantHash)
    Write-Host ('Verified fixed-lot profile: ' + $presetHash)
    Write-Host ('Verified unchanged upstream: ' + $originalHash)
    if ($VerifyOnly) {
        Write-Host 'PASS: verified trial source, upstream source and research preset without touching MT5.'
        exit 0
    }
    $terminal = Find-Terminal
    Write-Host ('MT5 executable: ' + $terminal.Terminal)
    Write-Host ('MT5 data folder: ' + $terminal.Data)
    $expertDir = Join-Path $terminal.Data 'MQL5\Experts\TraderResearch'
    $profileDir = Join-Path $terminal.Data 'MQL5\Profiles\Tester'
    $target = Join-Path $expertDir 'nyao_scalper_entry_gate.mq5'
    $binary = Join-Path $expertDir 'nyao_scalper_entry_gate.ex5'
    $profileTarget = Join-Path $profileDir 'Trader_ENTRY_GATE_FIXED001.set'
    $runDir = Join-Path $repo ('local_runs\entry_quality\' + (Get-Date -Format 'yyyyMMdd_HHmmss_fff'))
    $backup = Join-Path $runDir 'backup'
    New-Item -ItemType Directory -Path $expertDir,$profileDir,$runDir -Force | Out-Null
    foreach ($old in @($target, $binary, $profileTarget)) {
        if (Test-Path -LiteralPath $old -PathType Leaf) {
            New-Item -ItemType Directory -Path $backup -Force | Out-Null
            Copy-Item -LiteralPath $old -Destination (Join-Path $backup ([IO.Path]::GetFileName($old))) -ErrorAction Stop
        }
    }
    Copy-Item -LiteralPath $variant -Destination $target -Force -ErrorAction Stop
    Copy-Item -LiteralPath $preset -Destination $profileTarget -Force -ErrorAction Stop
    if ((Get-FileHash $target -Algorithm SHA256).Hash.ToLowerInvariant() -ne $variantHash -or
        (Get-FileHash $profileTarget -Algorithm SHA256).Hash.ToLowerInvariant() -ne $presetHash) {
        throw 'Copied file fingerprint mismatch; compilation aborted.'
    }
    if (Test-Path -LiteralPath $binary -PathType Leaf) { Remove-Item -LiteralPath $binary -Force }
    $compileStart = Get-Date
    Write-Host 'Compiling research variant using installed MetaEditor...'
    $args = @('/compile:"' + $target + '"','/log')
    $process = Start-Process -FilePath $terminal.Editor -ArgumentList $args -Wait -PassThru
    $compileLog = [IO.Path]::ChangeExtension($target,'.log')
    $logText = if (Test-Path -LiteralPath $compileLog -PathType Leaf) {
        Get-Content -LiteralPath $compileLog -Raw
    } else { '' }
    if ($logText) { Copy-Item -LiteralPath $compileLog -Destination (Join-Path $runDir 'compile.log') -Force }
    if ($process.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $binary -PathType Leaf) -or
        $logText -match '(?im)\b[1-9]\d* errors?\b' -or
        (Test-Path -LiteralPath $binary -PathType Leaf) -and (Get-Item -LiteralPath $binary).LastWriteTime -lt $compileStart.AddSeconds(-3)) {
        throw ('MetaEditor compilation failed or a NEW EX5 was not created. Inspect ' + (Join-Path $runDir 'compile.log'))
    }
    $receipt = [ordered]@{
        verdict = 'TRIAL_COMPILED_NOT_BACKTESTED_NOT_LIVE_APPROVED'
        source_sha256 = $variantHash
        ex5_sha256 = (Get-FileHash -LiteralPath $binary -Algorithm SHA256).Hash.ToLowerInvariant()
        preset_sha256 = $presetHash
        upstream_sha256 = $originalHash
        source_file = $target
        tester_profile = $profileTarget
        mt5_terminal = $terminal.Terminal
        broker_orders_submitted = $false
    }
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [IO.File]::WriteAllText((Join-Path $runDir 'receipt.json'),($receipt | ConvertTo-Json -Depth 3),$utf8)
    Write-Host ''
    Write-Host 'SUCCESS: trial EA compiled separately. Original EA unchanged.'
    Write-Host ('Select Expert: TraderResearch\nyao_scalper_entry_gate')
    Write-Host ('Load tester Inputs preset: ' + $profileTarget)
    Write-Host ('Receipt and compile log: ' + $runDir)
    Write-Host 'No terminal opened, no testing initiated and no broker orders sent.'
    exit 0
} catch {
    Write-Host ('TRIAL SETUP STOPPED: ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host 'No trading was enabled. Original EA stays unchanged.'
    exit 2
}
