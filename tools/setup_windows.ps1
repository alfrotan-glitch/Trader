# Trader Windows setup: copy one pinned upstream MQL5 EA into the correct MT5 data folder,
# compile with the matching MetaEditor, then prepare a read-only Strategy Tester profile.
# NEVER attach an EA to a chart, activate Algo Trading, or send connected orders.
[CmdletBinding()]
param(
    [string]$TerminalPath = '',
    [string]$DataFolder = '',
    [string]$Symbol = 'XAUUSD@',
    [switch]$LaunchTester,
    [switch]$VerifyOnly
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$source = Join-Path $repo 'nyao_scalper.mq5'
$presetSource = Join-Path $repo 'settings\xauusd-default.set'
$expectedSourceSha256 = @('91ea11b70553fa413af9712745052fd192039e0627d8f7c3a34e066b80a1c837', 'f4d5a57075745d8dd41297e3b252b31bbc08996f2eec727c898c2165e3cc9e3b')
$expectedPresetSha256 = @('d9efe2aeac85f65f280d7c9218c4a2af7572a5f6da79abfd4fb61bd3596f6858', '9978e2930a05ce62dac63954c5bc24ce894041be6b195efce46bed8619b1c4aa')

function Require-File([string]$path, [string]$purpose) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw ("Missing " + $purpose + ": " + $path + ". Verify GitHub source import first.")
    }
}
function Canonical-Path([string]$path) {
    return ([System.IO.Path]::GetFullPath($path)).TrimEnd('\','/').ToLowerInvariant()
}
function Get-TerminalCandidate([string]$dataDir) {
    $originFile = Join-Path $dataDir 'origin.txt'
    if (-not (Test-Path -LiteralPath $originFile -PathType Leaf)) { return $null }
    $first = (Get-Content -LiteralPath $originFile -ErrorAction Stop | Select-Object -First 1)
    if ([string]::IsNullOrWhiteSpace($first)) { return $null }
    $origin = $first.Trim().Trim('"')
    if ($origin -match '(?i)terminal64\.exe$') {
        $terminal = $origin
    } else {
        $terminal = Join-Path $origin 'terminal64.exe'
    }
    if (-not (Test-Path -LiteralPath $terminal -PathType Leaf)) { return $null }
    $editor = Join-Path (Split-Path -Parent $terminal) 'metaeditor64.exe'
    if (-not (Test-Path -LiteralPath $editor -PathType Leaf)) { return $null }
    return [pscustomobject]@{ Terminal=$terminal; Editor=$editor; Data=$dataDir }
}
function Resolve-Terminal {
    $base = Join-Path $env:APPDATA 'MetaQuotes\Terminal'
    $found = @()
    if (Test-Path -LiteralPath $base -PathType Container) {
        foreach ($dir in @(Get-ChildItem -LiteralPath $base -Directory -ErrorAction Stop)) {
            $candidate = Get-TerminalCandidate $dir.FullName
            if ($null -ne $candidate) { $found += $candidate }
        }
    }
    if ($DataFolder -ne '') {
        $wantedData = Canonical-Path $DataFolder
        $found = @($found | Where-Object { (Canonical-Path $_.Data) -eq $wantedData })
    }
    if ($TerminalPath -ne '') {
        $wantedExe = Canonical-Path $TerminalPath
        if (Test-Path -LiteralPath $TerminalPath -PathType Container) {
            $wantedExe = Canonical-Path (Join-Path $TerminalPath 'terminal64.exe')
        }
        $found = @($found | Where-Object { (Canonical-Path $_.Terminal) -eq $wantedExe })
    }
    $found = @($found | Sort-Object Data -Unique)
    if ($found.Count -gt 1 -and $TerminalPath -eq '' -and $DataFolder -eq '') {
        $wm = @($found | Where-Object { $_.Terminal -match '(?i)wm.?markets' })
        if ($wm.Count -eq 1) { $found = $wm }
    }
    if ($found.Count -eq 0) {
        throw "No uniquely registered MetaTrader 5 data folder found. Open the intended WMMarkets MT5 once, then run setup. You can pass -DataFolder and -TerminalPath when needed."
    }
    if ($found.Count -ne 1) {
        Write-Host "Multiple MT5 installations detected:"
        foreach ($x in $found) { Write-Host ("  Terminal: " + $x.Terminal + " | Data: " + $x.Data) }
        throw "Cannot safely select a broker installation. Pass -DataFolder and -TerminalPath; nothing has been modified."
    }
    return $found[0]
}
function Set-RequiredPresetValue([string]$content,[string]$key,[string]$value) {
    $pattern = '(?m)^' + [regex]::Escape($key) + '=[^\r\n]*'
    if ([regex]::Matches($content, $pattern).Count -ne 1) {
        throw ("Upstream preset missing or duplicate key: " + $key)
    }
    return [regex]::Replace($content, $pattern, ($key + '=' + $value))
}
function Write-Utf8([string]$path,[string]$content) {
    [System.IO.File]::WriteAllText($path,$content,(New-Object System.Text.UTF8Encoding($false)))
}
function Backup-IfExists([string]$path,[string]$backupDirectory) {
    if (Test-Path -LiteralPath $path -PathType Leaf) {
        New-Item -ItemType Directory -Path $backupDirectory -Force | Out-Null
        Copy-Item -LiteralPath $path -Destination (Join-Path $backupDirectory ([System.IO.Path]::GetFileName($path))) -ErrorAction Stop
    }
}
try {
    Require-File $source 'upstream Nyao Scalper source'
    Require-File $presetSource 'upstream gold .set profile'
    $presetSha = (Get-FileHash -LiteralPath $presetSource -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($presetSha -notin $expectedPresetSha256) { throw ('Upstream gold preset checksum mismatch: ' + $presetSha) }
    Require-File (Join-Path $repo 'LICENSE') 'upstream BSD-3-Clause license'
    $actualSha = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualSha -notin $expectedSourceSha256) {
        throw ("Pinned upstream MQL5 SHA-256 mismatch. Expected " + $expectedSourceSha256 + ", actual " + $actualSha + ". Do not run unreviewed source.")
    }
    if (-not [string]::Equals($Symbol,'XAUUSD@',[System.StringComparison]::Ordinal)) {
        throw 'Only the explicitly checked WMMarkets symbol XAUUSD@ is supported by this research launcher.'
    }
    if ($LaunchTester) {
        throw 'UNSAFE_AUTO_LAUNCH_DISABLED: The MT5 tester failed broker/symbol synchronization and the terminal became unresponsive. Do not auto-launch; use RUN_TESTER.bat for read-only diagnostics and test manually in DEMO MT5.'
    }
    $terminal = Resolve-Terminal
    Write-Host ("Terminal: " + $terminal.Terminal)
    Write-Host ("Data:     " + $terminal.Data)
    Write-Host ("Source:   " + $actualSha)
    $expertDir = Join-Path $terminal.Data 'MQL5\Experts\Trader'
    $testerDir = Join-Path $terminal.Data 'MQL5\Profiles\Tester'
    $target = Join-Path $expertDir 'nyao_scalper.mq5'
    $compiled = Join-Path $expertDir 'nyao_scalper.ex5'
    $setTarget = Join-Path $testerDir 'Trader_XAUUSD_M5_RESEARCH.set'
    $stamp = Get-Date -Format 'yyyyMMdd_HHmmss_fff'
    $runDir = Join-Path $repo ('local_runs\' + $stamp)
    $backupDir = Join-Path $runDir 'backup'
    if ($VerifyOnly) {
        Write-Host 'VERIFY ONLY: source SHA, license and installed terminal identity passed. No files changed.'
        exit 0
    }
    New-Item -ItemType Directory -Path $expertDir,$testerDir,$runDir -Force | Out-Null
    Backup-IfExists $target $backupDir
    Backup-IfExists $compiled $backupDir
    Backup-IfExists $setTarget $backupDir
    Copy-Item -LiteralPath $source -Destination $target -Force -ErrorAction Stop
    if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant() -ne $actualSha) {
        throw 'Source copy checksum mismatch. Compilation refused.'
    }
    if (Test-Path -LiteralPath $compiled) {
        Remove-Item -LiteralPath $compiled -Force -ErrorAction Stop
    }
    $compileStart = Get-Date
    $compileArgs = @('/compile:"' + $target + '"','/log')
    Write-Host 'Compiling source with the matching MetaEditor...'
    $proc = Start-Process -FilePath $terminal.Editor -ArgumentList $compileArgs -Wait -PassThru
    $compileLog = [System.IO.Path]::ChangeExtension($target,'.log')
    $compileText = if (Test-Path -LiteralPath $compileLog) { Get-Content -LiteralPath $compileLog -Raw } else { '' }
    if ($compileText -ne '') { Write-Utf8 (Join-Path $runDir 'compile.log') $compileText }
    if ($proc.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $compiled -PathType Leaf) -or
        $compileText -match '(?im)\b[1-9]\d* errors?\b' -or
        (Test-Path -LiteralPath $compiled -PathType Leaf) -and (Get-Item -LiteralPath $compiled).LastWriteTime -lt $compileStart.AddSeconds(-3)) {
        throw ("MetaEditor compilation did not yield a clean NEW EX5. Review " + (Join-Path $runDir 'compile.log') + ". The old binary remains backed up, not automatically restored.")
    }
    Write-Host ("Compiled: " + $compiled)
    $set = Get-Content -LiteralPath $presetSource -Raw -Encoding UTF8
    $changes = [ordered]@{
        'EnableHedgeChain' = 'false'
        'EnableStopLoss' = 'true'
        'EnableMaxSpreadFilter' = 'true'
        'RiskPerTradePct' = '1.0'
        'MaxRiskPerTradePct' = '1.0'
        'MaxOpenOrders' = '1'
        'MaxLotSize' = '0.02'
    }
    foreach ($key in $changes.Keys) { $set = Set-RequiredPresetValue $set $key $changes[$key] }
    $header = '; TRADER RESEARCH ONLY. Modified risk settings; NOT equivalent to vendor historical runs.' + [Environment]::NewLine
    Write-Utf8 $setTarget ($header + $set)
    Write-Utf8 (Join-Path $runDir 'Trader_XAUUSD_M5_RESEARCH.set') ($header + $set)
    $from = (Get-Date).AddMonths(-3).ToString('yyyy.MM.dd')
    $to = (Get-Date).AddDays(-1).ToString('yyyy.MM.dd')
    $iniPath = Join-Path $runDir 'tester.ini'
    $reportBase = Join-Path $runDir 'Nyao_M5_RealTicks'
    $ini = @(
      '[Tester]'
      'Expert=Trader\nyao_scalper'
      'ExpertParameters=Trader_XAUUSD_M5_RESEARCH.set'
      ('Symbol=' + $Symbol)
      'Period=M5'
      'Model=4'
      'Optimization=0'
      'UseCloud=0'
      'Visual=0'
      'Deposit=3000'
      ('FromDate=' + $from)
      ('ToDate=' + $to)
      ('Report=' + $reportBase)
      'ReplaceReport=0'
      'ShutdownTerminal=1'
    ) -join [Environment]::NewLine
    Write-Utf8 $iniPath ($ini + [Environment]::NewLine)
    $metadata = @{
      status = 'COMPILED_TEST_PREPARED_NOT_A_LIVE_PERMISSION'
      source_sha256 = $actualSha
      terminal = $terminal.Terminal
      data_folder = $terminal.Data
      compiled_sha256 = (Get-FileHash -LiteralPath $compiled -Algorithm SHA256).Hash.ToLowerInvariant()
      strategy_tester_config = $iniPath
      tester_preset = $setTarget
      symbol = $Symbol
      live_order_authorized = $false
      forward_edge_validated = $false
    }
    Write-Utf8 (Join-Path $runDir 'setup_result.json') ($metadata | ConvertTo-Json -Depth 4)
    Write-Host ''
    Write-Host 'SUCCESS: main EA installed and compiled, conservative TESTER preset prepared.'
    Write-Host ("Tester configuration: " + $iniPath)
    Write-Host 'No chart was attached; Algo Trading was NOT enabled; no broker order was sent.'
    exit 0
}
catch {
    Write-Host ''
    Write-Host ('STOPPED: ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host 'No automation enabling real trading was performed.'
    exit 2
}
