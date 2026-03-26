$ErrorActionPreference = "Stop"
$python = Join-Path $PSScriptRoot ".venv311\Scripts\python.exe"

if (-not (Test-Path $python)) {
    throw "Python not found at $python"
}

Write-Host "Starting FastAPI on port 8000..."
Start-Process -FilePath $python -WorkingDirectory $PSScriptRoot -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-keep-alive", "120"

Write-Host "Starting Streamlit on port 8501..."
Start-Process -FilePath $python -WorkingDirectory $PSScriptRoot -ArgumentList "-m", "streamlit", "run", "ui/app.py", "--server.port", "8501"

Write-Host "Both services launched."
