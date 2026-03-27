$ErrorActionPreference = "Stop"
$python = Join-Path $PSScriptRoot ".venv311\Scripts\python.exe"

if (-not (Test-Path $python)) {
    $python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path $python)) {
        throw "Python not found in .venv311 or .venv"
    }
}

Write-Host "Starting FastAPI on port 8000..."
Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-Command", "& '$python' -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --timeout-keep-alive 120" -WorkingDirectory $PSScriptRoot

Write-Host "Waiting for FastAPI to start..."
Start-Sleep -Seconds 4

Write-Host "Opening MarketAI Pro UI..."
Start-Process "http://localhost:8000/ui"

Write-Host ""
Write-Host "MarketAI Pro is running!"
Write-Host "  API:      http://localhost:8000"
Write-Host "  Frontend: http://localhost:8000/ui"
Write-Host ""
Write-Host "(Streamlit is no longer the primary UI - use the URL above)"
