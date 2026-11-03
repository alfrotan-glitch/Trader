# MT5 diagnostic: READ ONLY. Never launches or stops trading software.
[CmdletBinding()]
param([string]$TerminalDataFolder = '')
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Find-LatestLog([string]$folder) {
    if (-not (Test-Path -LiteralPath $folder -PathType Container)) { return $null }
    return (Get-ChildItem -LiteralPath $folder -Filter '*.log' -File -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1)
}
function Show-Messages([string]$file) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { return }
    Write-Host ('Journal: ' + $file)
    try {
        $raw = [System.IO.File]::ReadAllBytes($file)
        if ($raw.Length -gt 2 -and $raw[0] -eq 255 -and $raw[1] -eq 254) {
            $text = [System.Text.Encoding]::Unicode.GetString($raw, 2, $raw.Length-2)
        } else {
            $text = [System.Text.Encoding]::UTF8.GetString($raw)
        }
        $matches = @($text -split '`r?`n' | Where-Object {
            $_ -match '(?i)not synchronized|cannot select symbol|no connection|disconnected|connected|authorization|invalid account|failed|error|nyao_scalper|test started|test finished|automatic testing'
        } | Select-Object -Last 30)
        if ($matches.Count -eq 0) { Write-Host 'No matching messages.' }
        foreach ($line in $matches) { Write-Host $line }
    } catch {
        Write-Warning ('Journal read failed: ' + $_.Exception.Message)
    }
}

Write-Host '=== TRADER: READ-ONLY MT5 INCIDENT REPORT ==='
Write-Host 'No MT5 app will be started, restarted or closed.'
$root = Join-Path $env:APPDATA 'MetaQuotes\Terminal'
$installations = @()
if (Test-Path -LiteralPath $root -PathType Container) {
    foreach ($dir in @(Get-ChildItem -LiteralPath $root -Directory)) {
        if ($TerminalDataFolder -ne '' -and
            $dir.FullName.TrimEnd('\') -ine ([System.IO.Path]::GetFullPath($TerminalDataFolder)).TrimEnd('\')) { continue }
        $origin = Join-Path $dir.FullName 'origin.txt'
        if (-not (Test-Path -LiteralPath $origin -PathType Leaf)) { continue }
        $installations += $dir.FullName
    }
}
Write-Host ('Registered data folders: ' + $installations.Count)
$procs = @(Get-Process -Name terminal64,metatester64 -ErrorAction SilentlyContinue)
if ($procs.Count -eq 0) { Write-Host 'No terminal64/metatester64 process running.' }
foreach ($p in $procs) { Write-Host ('Process: ' + $p.ProcessName + ' PID=' + $p.Id) }
foreach ($folder in $installations) {
    Write-Host ('=== ' + $folder + ' ===')
    $terminalLog = Find-LatestLog (Join-Path $folder 'logs')
    $testerLog = Find-LatestLog (Join-Path $folder 'Tester\logs')
    if ($null -ne $terminalLog) { Show-Messages $terminalLog.FullName }
    if ($null -ne $testerLog) { Show-Messages $testerLog.FullName }
}
Write-Host '=== RECENT WINDOWS APP CRASH EVENTS ==='
try {
    $events = @(Get-WinEvent -FilterHashtable @{
        LogName='Application'; StartTime=(Get-Date).AddHours(-48); Id=@(1000,1001,1002)
    } -MaxEvents 120 -ErrorAction Stop | Where-Object {
        $_.Message -match '(?i)terminal64\.exe|metatester64\.exe'
    } | Select-Object -First 8)
    if ($events.Count -eq 0) { Write-Host 'No matching event found in most recent 120 events.' }
    foreach ($e in $events) {
        Write-Host ('Event ID=' + $e.Id + ' at ' + $e.TimeCreated)
        $short = @($e.Message -split '`r?`n' | Select-Object -First 6)
        foreach ($line in $short) { Write-Host $line }
    }
} catch {
    Write-Host ('Cannot read Windows Event Log: ' + $_.Exception.Message)
}
Write-Host ''
Write-Host 'CONFIRMED FROM INCIDENT LOG: trade server not synchronized; cannot select symbol in Market Watch.'
Write-Host 'These explain why the test did not begin, NOT why Windows marked the GUI unresponsive.'
Write-Host 'For crash cause inspect the Windows Event ID 1000/1001/1002 output above.'
Write-Host 'Safety block: RUN_TESTER no longer auto-launches MT5.'
Write-Host 'First open the intended MT5 manually using a DEMO account. Check its server connection.'
Write-Host 'In Market Watch check whether XAUUSD@ exists. Then use Ctrl+R to test Trader/nyao_scalper on M5.'
Write-Host 'Do not attach the EA to a live trading chart.'
exit 0
