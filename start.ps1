$ErrorActionPreference = "Stop"

$python = Join-Path $PSScriptRoot ".venv311\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path $python)) {
        throw "Python not found in .venv311 or .venv. Run: python -m venv .venv311"
    }
}

Write-Host "Using Python: $python"

$port = 8000
$existing = netstat -ano | Select-String ":$port " | Select-String "LISTENING"
if ($existing) {
    $tokens = ($existing -split "\s+") | Where-Object { $_ -match "^\d+$" } | Select-Object -Last 1
    if ($tokens) {
        Write-Host "Killing stale process on port $port (PID $tokens)..."
        Stop-Process -Id $tokens -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 1
    }
}

Write-Host "Starting FastAPI on port $port..."
$cmd = "& '$python' -m uvicorn app.main:app --host 127.0.0.1 --port $port --reload --timeout-keep-alive 120"
Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-Command", $cmd -WorkingDirectory $PSScriptRoot

Write-Host "Waiting for FastAPI to start..."
Start-Sleep -Seconds 5

Write-Host "Opening MarketAI Pro UI..."
Start-Process "http://127.0.0.1:$port/ui/"

Write-Host ""
Write-Host "MarketAI Pro is running!"
Write-Host "  API:      http://127.0.0.1:$port"
Write-Host "  Frontend: http://127.0.0.1:$port/ui/"
