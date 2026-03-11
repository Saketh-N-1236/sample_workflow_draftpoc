# Script to run dependency extraction with proper environment variable
param(
    [Parameter(Mandatory=$false)]
    [string]$SchemaName = "test_repo_17f1584c"
)

$env:TEST_REPO_SCHEMA = $SchemaName

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Running Dependency Extraction" -ForegroundColor Cyan
Write-Host "Schema: $SchemaName" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Step 1: Extracting Static Dependencies..." -ForegroundColor Yellow
python test_analysis/04_extract_static_dependencies.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ❌ Dependency extraction failed" -ForegroundColor Red
    exit 1
}
Write-Host ""

Write-Host "Step 2: Building Reverse Index..." -ForegroundColor Yellow
python test_analysis/06_build_reverse_index.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ❌ Reverse index build failed" -ForegroundColor Red
    exit 1
}
Write-Host ""

Write-Host "Step 3: Loading Dependencies to Database..." -ForegroundColor Yellow
python deterministic/03_load_dependencies.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ❌ Loading dependencies failed" -ForegroundColor Red
    exit 1
}
Write-Host ""

Write-Host "Step 4: Loading Reverse Index to Database..." -ForegroundColor Yellow
python deterministic/04_load_reverse_index.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ❌ Loading reverse index failed" -ForegroundColor Red
    exit 1
}
Write-Host ""

Write-Host "=========================================" -ForegroundColor Green
Write-Host "Dependency Extraction Complete!" -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Green
