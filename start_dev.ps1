# Launches both Backend and Frontend in separate PowerShell windows
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host " VisionCore 2.0 - Local Development Starter" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# 1. Start Backend in a new window
Write-Host "Launching Backend on http://127.0.0.1:8000..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", "`"$ScriptDir\start_backend.ps1`""

# Brief delay to allow backend to initialize
Start-Sleep -Seconds 3

# 2. Start Frontend in a new window
Write-Host "Launching Frontend on http://localhost:5173..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", "`"$ScriptDir\start_frontend.ps1`""

Write-Host "`nBoth services launched in separate windows!" -ForegroundColor Cyan
Write-Host "Backend API:  http://127.0.0.1:8000/docs" -ForegroundColor White
Write-Host "Frontend App: http://localhost:5173" -ForegroundColor White
