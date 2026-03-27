$ErrorActionPreference = "Stop"
$python = Join-Path $PSScriptRoot ".venv311\Scripts\python.exe"

if (-not (Test-Path $python)) {
    # Fallback to .venv if .venv311 is not found
    $python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path $python)) {
        throw "Python not found in .venv311 or .venv"
    }
}

Write-Host "Starting FastAPI on port 8000..."
Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-Command", "& '$python' -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --timeout-keep-alive 120" -WorkingDirectory $PSScriptRoot

Start-Sleep -Seconds 2

Write-Host "Starting Streamlit on port 8501..."
Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-Command", "& '$python' -m streamlit run ui/app.py --server.port 8501" -WorkingDirectory $PSScriptRoot

Write-Host "Both services launched. Check the two new terminal windows for logs."
Write-Host "FastAPI: http://localhost:8000"
Write-Host "Streamlit: http://localhost:8501"
