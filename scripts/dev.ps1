$ErrorActionPreference = "Stop"

Write-Host "Starting Postgres (Docker)..."
docker compose up -d

Write-Host "Starting API..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", @"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r services/api/requirements.txt
python -m playwright install chromium
uvicorn services.api.app.main:app --reload --port 8000
"@

Write-Host "Starting Web..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", @"
cd apps/web
npm install
npm run dev
"@
