# Starts the VisionCore2.0 FastAPI Backend on Windows
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location "$ScriptDir\backend"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host " Starting VisionCore 2.0 Backend (FastAPI)" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

$PythonExe = "$ScriptDir\backend\.venv\Scripts\python.exe"

if (-not (Test-Path $PythonExe)) {
    Write-Error "Virtual environment not found at $ScriptDir\backend\.venv. Run dev_setup.ps1 first."
    exit 1
}

Write-Host "Backend running at: http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "API Documentation:  http://127.0.0.1:8000/docs" -ForegroundColor Green
Write-Host "Health check:       http://127.0.0.1:8000/health" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop.`n" -ForegroundColor Yellow

& $PythonExe -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
