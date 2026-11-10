# BingoCode IDE process monitor (Windows)
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File scripts/watch-ide-processes.ps1 [-IntervalSeconds 2]
#
# Why: WebView2 renderer/GPU processes (msedgewebview2.exe) are spawned by the shared
# system runtime and get mixed with other apps in Task Manager. They can only be told
# apart by the --user-data-folder command line flag, which contains our app identifier
# (com.bingocode.ide). Python / PowerShell children are attributed via parent-PID chain.

param(
    [double]$IntervalSeconds = 2
)

$AppIdentifier = 'com.bingocode.ide'
$MainProcessNames = @('bingo-ide', 'BingoCode', 'BingoCodeIDE', 'app')  # packaged exe is bingo-ide.exe; tauri dev binary is app.exe

function Get-IdeProcessTree {
    $all = Get-CimInstance Win32_Process

    $result = New-Object System.Collections.Generic.List[object]

    # 1. Main process (BingoCode.exe / app.exe)
    foreach ($r in @($all | Where-Object { $MainProcessNames -contains ($_.Name -replace '\.exe$','') })) {
        $result.Add([pscustomobject]@{ Id = $r.ProcessId; Name = $r.Name; Role = 'main'; Raw = $r })
    }

    # 2. WebView2: match --user-data-folder in command line
    foreach ($w in @($all | Where-Object {
        $_.Name -eq 'msedgewebview2.exe' -and $_.CommandLine -like "*$AppIdentifier*"
    })) {
        $role = 'webview2'
        if ($w.CommandLine -match '--type=gpu-process') { $role = 'webview2-gpu' }
        elseif ($w.CommandLine -match '--type=renderer')  { $role = 'webview2-renderer' }
        elseif ($w.CommandLine -match '--type=utility')   { $role = 'webview2-utility' }
        elseif ($w.CommandLine -notmatch '--type=')       { $role = 'webview2-browser' }
        $result.Add([pscustomobject]@{ Id = $w.ProcessId; Name = $w.Name; Role = $role; Raw = $w })
    }

    # 3. Child process chain (python.exe / powershell.exe / conhost ...) by parent PID
    $known = @{}; foreach ($r in $result) { $known[$r.Id] = $true }
    $changed = $true
    while ($changed) {
        $changed = $false
        foreach ($p in $all) {
            if ($known.ContainsKey($p.ProcessId)) { continue }
            if ($p.ParentProcessId -and $known.ContainsKey([int]$p.ParentProcessId)) {
                $role = 'child'
                if ($p.Name -match '^python')          { $role = 'python-engine' }
                elseif ($p.Name -match 'powershell')   { $role = 'powershell-terminal' }
                $result.Add([pscustomobject]@{ Id = $p.ProcessId; Name = $p.Name; Role = $role; Raw = $p })
                $known[$p.ProcessId] = $true
                $changed = $true
            }
        }
    }
    return $result
}

while ($true) {
    $procs = Get-IdeProcessTree
    $ids = $procs | ForEach-Object { $_.Id }
    $perf = @{}
    if ($ids.Count -gt 0) {
        foreach ($p in Get-Process -Id $ids -ErrorAction SilentlyContinue) {
            $perf[[int]$p.Id] = $p
        }
    }

    Clear-Host
    Write-Host ("BingoCode IDE process monitor  {0}  (Ctrl+C to quit)" -f (Get-Date -Format 'HH:mm:ss')) -ForegroundColor Green
    Write-Host ("{0,-8} {1,-22} {2,-20} {3,10} {4,12}" -f 'PID','Name','Role','CPU(s)','Mem(MB)')
    Write-Host ('-' * 76)

    $totalCpu = 0.0; $totalMem = 0.0
    foreach ($r in ($procs | Sort-Object Role, Name)) {
        $cpu = ''; $mem = ''
        $key = [int]$r.Id
        if ($perf.ContainsKey($key)) {
            $cpu = '{0,10:N1}' -f $perf[$key].CPU
            $mem = '{0,12:N1}' -f ($perf[$key].WorkingSet64 / 1MB)
            $totalCpu += $perf[$key].CPU
            $totalMem += $perf[$key].WorkingSet64 / 1MB
        }
        Write-Host ("{0,-8} {1,-22} {2,-20} {3} {4}" -f $r.Id, $r.Name, $r.Role, $cpu, $mem)
    }
    Write-Host ('-' * 76)
    Write-Host ("{0,-8} {1,-22} {2,-20} {3,10:N1} {4,12:N1}" -f '', ("TOTAL ({0} procs)" -f $procs.Count), '', $totalCpu, $totalMem) -ForegroundColor Cyan

    Start-Sleep -Seconds $IntervalSeconds
}
