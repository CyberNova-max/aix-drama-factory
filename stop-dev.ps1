$ErrorActionPreference = 'Stop'
$devRoot = [IO.Path]::GetFullPath($PSScriptRoot).TrimEnd('\')
if (-not (Test-Path -LiteralPath (Join-Path $devRoot 'app.py'))) {
    throw "Development root check failed: app.py was not found in $devRoot"
}

$rules = @{
    7862 = 'app\.py'
    8190 = 'ComfyUI\\main\.py'
    8085 = 'llama-server\.exe'
}

foreach ($port in $rules.Keys) {
    $lines = netstat -ano -p tcp | Select-String "127\.0\.0\.1:$port\s+.*LISTENING"
    foreach ($line in $lines) {
        $pidValue = [int](($line.ToString() -split '\s+')[-1])
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$pidValue"
        $exe = [IO.Path]::GetFullPath([string]$proc.ExecutablePath)
        $cmd = [string]$proc.CommandLine
        if (-not $exe.StartsWith($devRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
            Write-Warning "Skip port $port PID ${pidValue}: executable is outside V2 DEV ($exe)"
            continue
        }
        if ($cmd -notmatch $rules[$port]) {
            Write-Warning "Skip port $port PID ${pidValue}: command line does not match the V2 service"
            continue
        }
        Stop-Process -Id $pidValue -Force
        Write-Host "[OK] Stopped V2 DEV service on port $port (PID $pidValue)"
    }
}

Write-Host '[DONE] V2 DEV GPU and web services are stopped. Stable services were not touched.'
