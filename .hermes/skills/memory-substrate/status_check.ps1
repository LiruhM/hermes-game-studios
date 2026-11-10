# Hermes-Corp Stack - Status Check
# Quick health check for all services

param()

Write-Host "🏥 Hermes-Corp Stack Status Check" -ForegroundColor Cyan
Write-Host "=================================" -ForegroundColor Cyan

function Check-Service {
    param($url, $name, $port)
    try {
        $response = Invoke-WebRequest -Uri $url -Method GET -TimeoutSec 3 -ErrorAction Stop
        if ($response.StatusCode -eq 200) {
            Write-Host "✅ $name ($port) - HEALTHY" -ForegroundColor Green
            return $true
        }
    } catch {
        Write-Host "❌ $name ($port) - DOWN" -ForegroundColor Red
        return $false
    }
}

Write-Host ""
Write-Host "🏥 Health Checks:" -ForegroundColor Yellow
$results = @()
$results += Check-Service "http://127.0.0.1:8767/health" "Memory Substrate" 8767
$results += Check-Service "http://127.0.0.1:8081/health" "Game Server" 8081
$results += Check-Service "http://127.0.0.1:8080" "Frontend" 8080
$results += Check-Service "http://127.0.0.1:3120/rpc" "Supervisor RPC" 3120

Write-Host ""
Write-Host "🔌 WebSocket Test:" -ForegroundColor Yellow
try {
    $ws = New-Object System.Net.WebSockets.ClientWebSocket
    $cts = New-Object System.Threading.CancellationTokenSource
    $cts.CancelAfter(5000)
    $task = $ws.ConnectAsync("ws://127.0.0.1:8080/ws", $cts.Token)
    if ($task.Wait(5000) -and $ws.State -eq "Open") {
        Write-Host "✅ WebSocket (8080/ws proxy) - CONNECTED" -ForegroundColor Green
    } else {
        Write-Host "❌ WebSocket (8080/ws proxy) - FAILED" -ForegroundColor Red
    }
} catch {
    Write-Host "❌ WebSocket - ERROR: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "📋 Quick Access:" -ForegroundColor Cyan
Write-Host "  🌐 Frontend:     http://127.0.0.1:8080"
Write-Host "  🎮 Game Server:  ws://127.0.0.1:8081/ws | http://127.0.0.1:8081/health"
Write-Host "  🧠 Memory:       http://127.0.0.1:8767/health"
Write-Host "  🤖 Supervisor:   http://127.0.0.1:3120/rpc"
Write-Host "  🧠 Memory Sub:   http://127.0.0.1:8767"
Write-Host ""