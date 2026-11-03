# Read-only installation: copies and compiles a tester-only research EA. NEVER starts terminal.
[CmdletBinding()]
param(
    [string]$TerminalPath = '',
    [string]$DataFolder = '',
    [switch]$VerifyOnly
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$diagDir = Join-Path $repo 'research\diagnostics'
$source = Join-Path $diagDir 'nyao_scalper_diagnostic.mq5'
$header = Join-Path $diagDir 'NYAO_Diagnostics.mqh'
$profile = Join-Path $repo 'research\fresh_entry\Trader_FRESH_ER015_FIXED001.set'
$original = Join-Path $repo 'nyao_scalper.mq5'

function File-SHA([string]$path) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw ('Missing file: ' + $path) }
    return (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
}
function Canonical([string]$path) {
    return [IO.Path]::GetFullPath($path).TrimEnd('\','/').ToLowerInvariant()
}
function Find-Terminal {
    $root = Join-Path $env:APPDATA 'MetaQuotes\Terminal'
    $found = @()
    if (Test-Path -LiteralPath $root -PathType Container) {
        foreach ($dir in @(Get-ChildItem -LiteralPath $root -Directory)) {
            $origin = Join-Path $dir.FullName 'origin.txt'
            if (-not (Test-Path -LiteralPath $origin -PathType Leaf)) { continue }
            $line = Get-Content -LiteralPath $origin | Select-Object -First 1
            if ([string]::IsNullOrWhiteSpace($line)) { continue }
            $exe = $line.Trim().Trim('"')
            if ($exe -notmatch '(?i)terminal64\.exe$') { $exe = Join-Path $exe 'terminal64.exe' }
            $editor = Join-Path (Split-Path -Parent $exe) 'metaeditor64.exe'
            if ((Test-Path -LiteralPath $exe -PathType Leaf) -and (Test-Path -LiteralPath $editor -PathType Leaf)) {
                $found += [pscustomobject]@{ Terminal = $exe; Editor = $editor; Data = $dir.FullName }
            }
        }
    }
    if ($DataFolder -ne '') {
        $wanted = Canonical $DataFolder
        $found = @($found | Where-Object { (Canonical $_.Data) -eq $wanted })
    }
    if ($TerminalPath -ne '') {
        $wantedExe = $TerminalPath
        if (Test-Path -LiteralPath $wantedExe -PathType Container) {
            $wantedExe = Join-Path $wantedExe 'terminal64.exe'
        }
        $wanted = Canonical $wantedExe
        $found = @($found | Where-Object { (Canonical $_.Terminal) -eq $wanted })
    }
    $found = @($found | Sort-Object Data -Unique)
    if ($found.Count -ne 1) {
        foreach ($item in $found) { Write-Host ('Candidate MT5: ' + $item.Terminal + ' -> ' + $item.Data) }
        throw 'MT5 not found or multiple terminals. Open DEMO MT5 once or specify -DataFolder. No MT5 files changed.'
    }
    return $found[0]
}

try {
    Write-Host 'NYAO DIAGNOSTIC: copy/compile only; tester-only; LIVE LOCKED.'
    $origHash = File-SHA $original
    if ($origHash -notin @(
      '91ea11b70553fa413af9712745052fd192039e0627d8f7c3a34e066b80a1c837',
      'f4d5a57075745d8dd41297e3b252b31bbc08996f2eec727c898c2165e3cc9e3b'
    )) { throw 'Original Nyao source changed; refusing experimental compile.' }
    $sourceHash = File-SHA $source
    $headerHash = File-SHA $header
    $profileHash = File-SHA $profile

    $profileText = Get-Content -LiteralPath $profile -Raw -ErrorAction Stop
    $pairs = [regex]::Matches($profileText, '(?m)^([A-Za-z_][A-Za-z0-9_]*)=([^\r\n]*)\r?$')
    if ($pairs.Count -ne 172) { throw ('Expected exactly 172 preset inputs, got ' + $pairs.Count) }
    foreach ($exact in @('MinEfficiencyToTrade=0.15','BaseLotSize=0.01','MaxOpenOrders=1',
                         'RiskPerTradePct=0.0','EnableLossManagement=false','EnableLimitEntry=false',
                         'EnableHedgeChain=false','DrawdownScope=1')) {
        if ($profileText -notmatch ('(?m)^' + [regex]::Escape($exact) + '\r?$')) {
            throw ('Research preset is not frozen: expected ' + $exact)
        }
    }
    $srcText = Get-Content -LiteralPath $source -Raw -ErrorAction Stop
    if ($srcText -notmatch 'if\(!MQLInfoInteger\(MQL_TESTER\) \|\| MQLInfoInteger\(MQL_OPTIMIZATION\)\)' -or
        $srcText -notmatch '#include "NYAO_Diagnostics\.mqh"') {
        throw 'Tester-only initialization guard or diagnostic module missing.'
    }

    Write-Host ('Original SHA256: ' + $origHash)
    Write-Host ('Diagnostic source SHA256: ' + $sourceHash)
    Write-Host ('Diagnostics header SHA256: ' + $headerHash)
    Write-Host ('Frozen profile SHA256: ' + $profileHash)
    if ($VerifyOnly) {
        Write-Host 'PASS: verified source, module, unchanged vendor EA, 172-input preset; no MT5 operations.'
        exit 0
    }

    $mt5 = Find-Terminal
    $expertDir = Join-Path $mt5.Data 'MQL5\Experts\TraderResearch'
    $testerProfileDir = Join-Path $mt5.Data 'MQL5\Profiles\Tester'
    $runDir = Join-Path $repo ('local_runs\diagnostics\' + (Get-Date -Format 'yyyyMMdd_HHmmss_fff'))
    $backup = Join-Path $runDir 'backup'
    $destSource = Join-Path $expertDir 'nyao_scalper_diagnostic.mq5'
    $destHeader = Join-Path $expertDir 'NYAO_Diagnostics.mqh'
    $destBinary = Join-Path $expertDir 'nyao_scalper_diagnostic.ex5'
    $destPreset = Join-Path $testerProfileDir 'Trader_FRESH_ER015_FIXED001.set'
    New-Item -ItemType Directory -Path $expertDir,$testerProfileDir,$runDir -Force | Out-Null
    foreach ($old in @($destSource,$destHeader,$destBinary,$destPreset)) {
        if (Test-Path -LiteralPath $old -PathType Leaf) {
            New-Item -ItemType Directory -Path $backup -Force | Out-Null
            Copy-Item -LiteralPath $old -Destination (Join-Path $backup ([IO.Path]::GetFileName($old)))
        }
    }
    Copy-Item -LiteralPath $source -Destination $destSource -Force
    Copy-Item -LiteralPath $header -Destination $destHeader -Force
    Copy-Item -LiteralPath $profile -Destination $destPreset -Force
    if ((File-SHA $destSource) -ne $sourceHash -or (File-SHA $destHeader) -ne $headerHash -or
        (File-SHA $destPreset) -ne $profileHash) {
        throw 'Copied research files failed checksum verification.'
    }
    if (Test-Path -LiteralPath $destBinary -PathType Leaf) {
        Remove-Item -LiteralPath $destBinary -Force
    }
    $compileStart = Get-Date
    $params = @('/compile:"' + $destSource + '"','/log')
    $p = Start-Process -FilePath $mt5.Editor -ArgumentList $params -Wait -PassThru
    $logPath = [IO.Path]::ChangeExtension($destSource, '.log')
    $logText = if (Test-Path -LiteralPath $logPath -PathType Leaf) {
        Get-Content -LiteralPath $logPath -Raw
    } else { '' }
    if ($logText) { Copy-Item -LiteralPath $logPath -Destination (Join-Path $runDir 'compile.log') -Force }
    if ($p.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $destBinary -PathType Leaf) -or
        $logText -match '(?im)\b[1-9]\d* errors?\b' -or
        ((Test-Path -LiteralPath $destBinary -PathType Leaf) -and
         (Get-Item -LiteralPath $destBinary).LastWriteTime -lt $compileStart.AddSeconds(-3))) {
        throw ('MetaEditor did not create a clean new EX5. Inspect: ' + (Join-Path $runDir 'compile.log'))
    }
    $receipt = [ordered]@{
        verdict = 'DIAGNOSTIC_COMPILED__NOT_BACKTESTED__LIVE_LOCKED'
        source_sha256 = $sourceHash
        module_sha256 = $headerHash
        preset_sha256 = $profileHash
        vendor_sha256 = $origHash
        ex5_sha256 = File-SHA $destBinary
        terminal = $mt5.Terminal
        data_folder = $mt5.Data
        profile = $destPreset
        output_csv_when_tested = Join-Path $env:APPDATA 'MetaQuotes\Terminal\Common\Files\NYAO_ENTRY_DIAGNOSTICS.csv'
        started_terminal = $false
        sent_orders = $false
    }
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [IO.File]::WriteAllText((Join-Path $runDir 'receipt.json'),($receipt | ConvertTo-Json -Depth 5),$utf8)
    Write-Host ''
    Write-Host 'PASS: compiled research-only EA. Main Nyao EA NOT replaced.'
    Write-Host 'In DEMO MT5 Strategy Tester select Expert: TraderResearch\nyao_scalper_diagnostic'
    Write-Host ('Load Inputs preset: ' + $destPreset)
    Write-Host ('CSV output after manual TEST: ' + $receipt.output_csv_when_tested)
    Write-Host ('Compile evidence: ' + $runDir)
    Write-Host 'Terminal was NOT launched; no orders were sent. LIVE remains LOCKED.'
    exit 0
} catch {
    Write-Host ('STOP: ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host 'This script cannot enable live trading and has not started the terminal.'
    exit 2
}
