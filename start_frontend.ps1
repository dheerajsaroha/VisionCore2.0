# Starts the VisionCore2.0 React/Vite Frontend on Windows
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location "$ScriptDir\frontend"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host " Starting VisionCore 2.0 Frontend (Vite)  " -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

Write-Host "Frontend running at: http://localhost:5173" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop.`n" -ForegroundColor Yellow

npm run dev
