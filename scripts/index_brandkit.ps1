param(
  [string]$ApiUrl = "http://localhost:8000",
  [string]$BrandKitDir = "brand-kit",
  [int]$EmbeddingDimension = 1024
)

$ErrorActionPreference = "Stop"

function Fail($msg) {
  Write-Host "[index_brandkit] ERROR: $msg" -ForegroundColor Red
  exit 1
}

if (-not (Test-Path $BrandKitDir)) {
  Fail "Cannot find '$BrandKitDir'. Run this from repo root, or pass -BrandKitDir <path>."
}

$files = Get-ChildItem -Path $BrandKitDir -Filter *.md -File
if ($files.Count -eq 0) {
  Fail "No .md files found in '$BrandKitDir'. Add files like brand-kit/tone.md, brand-kit/policies.md, etc."
}

$docs = @()
foreach ($f in $files) {
  $content = Get-Content $f.FullName -Raw
  $title = [System.IO.Path]::GetFileNameWithoutExtension($f.Name)

  $docs += @{
    title   = $title
    content = $content
    source  = "$BrandKitDir/$($f.Name)"
    tags    = @($title)
  }
}

$payload = @{
  docs = $docs
  embedding_dimension = $EmbeddingDimension
} | ConvertTo-Json -Depth 10

Write-Host "[index_brandkit] Indexing $($files.Count) docs into $ApiUrl/brandkit/index ..." -ForegroundColor Cyan

try {
  $resp = Invoke-RestMethod -Method Post -Uri "$ApiUrl/brandkit/index" -ContentType "application/json" -Body $payload
  Write-Host "[index_brandkit] Done." -ForegroundColor Green
  $resp | ConvertTo-Json -Depth 20
} catch {
  Fail $_.Exception.Message
}