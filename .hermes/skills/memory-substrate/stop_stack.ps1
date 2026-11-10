# Hermes-Corp Stack - Stop All Services
# Run this script to stop all services gracefully

param()

Write-Host "🛑 Stopping Hermes-Corp Stack..." -ForegroundColor Yellow

# Stop by PID file if exists
$pidFile = "$env:TEMP\hermes-pids.txt"
if (Test-Path $pidFile) {
    $pids = Get-Content $pidFile | ForEach-Object { $_ -replace '.*=(\d+)', '$1' }
    foreach ($pid in $pids) {
        try {
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
            Write-Host "✅ Stopped PID $pid" -ForegroundColor Green
        } catch {
            Write-Host "⚠️  PID $pid already stopped" -ForegroundColor Yellow
        }
    }
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
}

# Fallback: kill by port
$ports = @(8080, 8081, 8767, 3120)
foreach ($port in $ports) {
    $process = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty OwningProcess
    if ($process) {
        try {
            Stop-Process -Id $process -Force -ErrorAction SilentlyContinue
            Write-Host "✅ Stopped process on port $port (PID $process)" -ForegroundColor Green
        } catch {}
    }
}

Write-Host "✅ All services stopped" -ForegroundColor Green