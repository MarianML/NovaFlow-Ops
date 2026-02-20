$ErrorActionPreference = "Stop"

Write-Host "=== NovaFlow Ops Demo Script (Python 3.11) ==="

# -----------------------------
# Helpers
# -----------------------------
$PY = "py -3.11"

function Ensure-Venv {
    if (!(Test-Path ".venv")) {
        Write-Host "Creating virtual environment (.venv) with Python 3.11..."
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

function Wait-HttpOk([string]$Url, [int]$TimeoutSec = 30) {
    $start = Get-Date
    while ((Get-Date) - $start -lt (New-TimeSpan -Seconds $TimeoutSec)) {
        try {
            Invoke-RestMethod -Uri $Url -Method Get -TimeoutSec 3 | Out-Null
            return
        } catch {
            Start-Sleep -Seconds 1
        }
    }
    throw "Timeout waiting for $Url"
}

# -----------------------------
# 1. Start Postgres
# -----------------------------
Write-Host "Starting Postgres (Docker Compose)..."
docker compose up -d

Start-Sleep -Seconds 3

# -----------------------------
# 2. Setup Python environment (3.11)
# -----------------------------
Ensure-Venv

Write-Host "Installing API dependencies..."
python -m pip install -r services/api/requirements.txt

Write-Host "Installing Playwright Chromium..."
python -m playwright install chromium

# -----------------------------
# 3. Start API (background window)
# -----------------------------
Write-Host "Starting API (new PowerShell window)..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", @"
Set-Location '$PWD'
. .\.venv\Scripts\Activate.ps1
python -m uvicorn services.api.app.main:app --port 8000
"@

Write-Host "Waiting for API to be ready..."
Wait-HttpOk "http://localhost:8000/health" 45

# -----------------------------
# 4. Index Brand Kit
# -----------------------------
Write-Host "Indexing Brand Kit..."

$docs = @()
Get-ChildItem -Path ".\brand-kit\*.md" -File | ForEach-Object {
    $docs += @{
        title   = $_.BaseName
        content = Get-Content $_.FullName -Raw
        source  = "brand-kit/$($_.Name)"
        tags    = @($_.BaseName)
    }
}

$payload = @{
    docs = $docs
    embedding_dimension = 1024
} | ConvertTo-Json -Depth 10

Invoke-RestMethod -Method Post `
    -Uri http://localhost:8000/brandkit/index `
    -ContentType "application/json" `
    -Body $payload | Out-Null

# -----------------------------
# 5. Create demo task
# -----------------------------
Write-Host "Creating demo run..."

$taskPayload = @{
    task  = "Go to Form Authentication, login with tomsmith / SuperSecretPassword!, verify success text, then take a screenshot."
    top_k = 4
} | ConvertTo-Json

$response = Invoke-RestMethod -Method Post `
    -Uri http://localhost:8000/task `
    -ContentType "application/json" `
    -Body $taskPayload

$runId = $response.run_id
Write-Host "Run ID: $runId"

# -----------------------------
# 6. Execute UI steps
# -----------------------------
Write-Host "Executing UI steps..."
for ($i = 0; $i -lt 6; $i++) {
    Invoke-RestMethod -Method Post `
        -Uri "http://localhost:8000/runs/$runId/execute-next-ui-step" | Out-Null
    Start-Sleep -Seconds 2
}

# -----------------------------
# 7. Fetch run details
# -----------------------------
$runDetails = Invoke-RestMethod -Uri "http://localhost:8000/runs/$runId"
Write-Host "Demo completed."
Write-Host "Artifacts: http://localhost:8000/artifacts/"