$ErrorActionPreference = "Stop"

Write-Host "=== NovaFlow Ops Dev Script (Python 3.11) ==="

# -----------------------------
# Helpers
# -----------------------------
$PY = "py -3.11"

function Ensure-Venv {
    if (!(Test-Path ".venv")) {
        Write-Host "Creating Python virtual environment (.venv) with Python 3.11..."
        & $PY -m venv .venv
    }

    Write-Host "Activating virtual environment..."
    . .\.venv\Scripts\Activate.ps1

    $v = (python --version 2>&1)
    Write-Host "Active Python: $v"
    if ($v -notmatch "3\.11") {
        throw "Virtualenv is not using Python 3.11. Delete .venv and re-run this script."
    }
}

function File-HashString($path) {
    if (!(Test-Path $path)) { return "" }
    return (Get-FileHash $path -Algorithm SHA256).Hash
}

# -----------------------------
# 1. Start Postgres (Docker)
# -----------------------------
Write-Host "Starting Postgres (Docker Compose)..."
docker compose up -d
Start-Sleep -Seconds 3

# -----------------------------
# 2. Python API setup (idempotent)
# -----------------------------
Ensure-Venv

$reqFile = "services/api/requirements.txt"
$cacheDir = ".cache"
$reqHashFile = Join-Path $cacheDir "requirements.sha256"
$pwMarkerFile = Join-Path $cacheDir "playwright.chromium.installed"

if (!(Test-Path $cacheDir)) {
    New-Item -ItemType Directory -Path $cacheDir | Out-Null
}

# Install Python deps only if requirements changed
$reqHash = File-HashString $reqFile
$prevReqHash = if (Test-Path $reqHashFile) { (Get-Content $reqHashFile -Raw).Trim() } else { "" }

if ($reqHash -ne $prevReqHash) {
    Write-Host "Installing/updating API dependencies (requirements changed)..."
    python -m pip install -r $reqFile
    Set-Content -Path $reqHashFile -Value $reqHash
} else {
    Write-Host "API dependencies unchanged. Skipping pip install."
}

# Install Playwright Chromium only once (marker-based)
if (!(Test-Path $pwMarkerFile)) {
    Write-Host "Installing Playwright Chromium..."
    python -m playwright install chromium
    New-Item -ItemType File -Path $pwMarkerFile | Out-Null
} else {
    Write-Host "Playwright Chromium already installed. Skipping."
}

# -----------------------------
# 3. Start API (new PowerShell window)
# -----------------------------
Write-Host "Starting API (FastAPI / Uvicorn)..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", @"
Set-Location '$PWD'
. .\.venv\Scripts\Activate.ps1
python -m uvicorn services.api.app.main:app --reload --port 8000
"@

# -----------------------------
# 4. Start Web (new PowerShell window)
# -----------------------------
Write-Host "Starting Web (Next.js)..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", @"
Set-Location '$PWD\apps\web'
if (!(Test-Path 'node_modules')) {
  Write-Host 'Installing web dependencies (node_modules missing)...'
  npm install
} else {
  Write-Host 'node_modules exists. Skipping npm install.'
}
npm run dev
"@

Write-Host "Done."
Write-Host "Web UI:  http://localhost:3000"
Write-Host "API:     http://localhost:8000"
Write-Host "Docs:    http://localhost:8000/docs"
Write-Host "Health:  http://localhost:8000/health"