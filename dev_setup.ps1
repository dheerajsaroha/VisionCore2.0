# PowerShell Development Setup for VisionCore2.0 (Windows)
# ---------------------------------------------------------------
# This script sets up VisionCore 2.0 to run natively on Windows without Docker.

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host " VisionCore 2.0 - Local Windows Dev Setup" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# ---------------------------------------------------------------
# 1. Check Python and Node.js
# ---------------------------------------------------------------
Write-Host "`n[1/5] Checking Prerequisites..." -ForegroundColor Yellow

$PythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $PythonCmd) {
    Write-Error "Python is not installed or not in PATH. Please install Python 3.10+."
    exit 1
}
Write-Host "Found Python: $(python --version)" -ForegroundColor Green

$NodeCmd = Get-Command node -ErrorAction SilentlyContinue
if (-not $NodeCmd) {
    Write-Error "Node.js is not installed or not in PATH. Please install Node.js 18+."
    exit 1
}
Write-Host "Found Node: $(node --version)" -ForegroundColor Green

# ---------------------------------------------------------------
# 2. Setup Backend Virtual Environment & Dependencies
# ---------------------------------------------------------------
Write-Host "`n[2/5] Setting up Backend Virtual Environment..." -ForegroundColor Yellow
$BackendDir = "$ScriptDir\backend"
$VenvDir = "$BackendDir\.venv"
$PythonExe = "$VenvDir\Scripts\python.exe"

if (-not (Test-Path $VenvDir)) {
    Write-Host "Creating virtual environment at $VenvDir..." -ForegroundColor Gray
    python -m venv $VenvDir
}

if (-not (Test-Path "$VenvDir\Lib\site-packages\fastapi")) {
    Write-Host "Installing backend dependencies from requirements.txt..." -ForegroundColor Gray
    & "$VenvDir\Scripts\pip.exe" install --upgrade pip
    & "$VenvDir\Scripts\pip.exe" install -r "$BackendDir\requirements.txt"
} else {
    Write-Host "Backend dependencies already installed." -ForegroundColor Green
}

# ---------------------------------------------------------------
# 3. Setup Frontend Node Dependencies
# ---------------------------------------------------------------
Write-Host "`n[3/5] Setting up Frontend Dependencies..." -ForegroundColor Yellow
$FrontendDir = "$ScriptDir\frontend"

if (-not (Test-Path "$FrontendDir\node_modules")) {
    Write-Host "Running npm install in frontend..." -ForegroundColor Gray
    Push-Location $FrontendDir
    npm install
    Pop-Location
} else {
    Write-Host "Frontend node_modules already present." -ForegroundColor Green
}

# ---------------------------------------------------------------
# 4. Verify Database & Run Migrations
# ---------------------------------------------------------------
Write-Host "`n[4/5] Checking Database & Applying Migrations..." -ForegroundColor Yellow
Push-Location $BackendDir
try {
    & $PythonExe -m alembic upgrade head
    Write-Host "Database migrations up to date (head)." -ForegroundColor Green
} catch {
    Write-Warning "Could not run migrations automatically. Ensure PostgreSQL service is running."
}
Pop-Location

# ---------------------------------------------------------------
# 5. Ready!
# ---------------------------------------------------------------
Write-Host "`n[5/5] Setup Complete!" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "To run the application locally:" -ForegroundColor White
Write-Host "  1. Start both servers:    .\start_dev.ps1" -ForegroundColor Yellow
Write-Host "  2. Or start backend only: .\start_backend.ps1" -ForegroundColor Yellow
Write-Host "  3. Or start frontend only: .\start_frontend.ps1" -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Cyan
