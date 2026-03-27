$ErrorActionPreference = "Stop"

# Prefer .venv311 (which has all dependencies installed)
# Fall back to .venv if 311 doesn't exist
$python = Join-Path $PSScriptRoot ".venv311\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path $python)) {
        throw "Python not found in .venv311 or .venv — please run: python -m venv .venv311 && .venv311\Scripts\pip install -r requirements.txt"
    }
}

Write-Host "Using Python: $python"

# Kill any existing server on port 8000
$existing = netstat -ano | Select-String ":8000 " | Select-String "LISTENING"
if ($existing) {
    $pid = ($existing -split "\s+")[-1]
    Write-Host "Killing existing process on port 8000 (PID $pid)..."
    Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
}

Write-Host "Starting FastAPI on port 8000..."
Start-Process -FilePath "powershell.exe" `
    -ArgumentList "-NoExit", "-Command", "& '$python' -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --timeout-keep-alive 120" `
    -WorkingDirectory $PSScriptRoot

Write-Host "Waiting for FastAPI to start..."
Start-Sleep -Seconds 5

Write-Host "Opening MarketAI Pro UI..."
Start-Process "http://127.0.0.1:8000/ui/"

Write-Host ""
Write-Host "MarketAI Pro is running!"
Write-Host "  API:      http://127.0.0.1:8000"
Write-Host "  Frontend: http://127.0.0.1:8000/ui/"
Write-Host ""
Write-Host "(Streamlit is no longer the primary UI - use the URL above)"
