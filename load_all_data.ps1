# Script to load all analysis data into database for a test repository
# Usage: .\load_all_data.ps1 -SchemaName "test_repo_17f1584c"

param(
    [Parameter(Mandatory=$true)]
    [string]$SchemaName
)

$env:TEST_REPO_SCHEMA = $SchemaName

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Loading All Data for Schema: $SchemaName" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

$scripts = @(
    @{Name="01_create_tables.py"; Desc="Creating database tables"},
    @{Name="02_load_test_registry.py"; Desc="Loading test registry"},
    @{Name="03_load_dependencies.py"; Desc="Loading dependencies"},
    @{Name="04_load_reverse_index.py"; Desc="Loading reverse index"},
    @{Name="04b_load_function_mappings.py"; Desc="Loading function mappings"},
    @{Name="05_load_metadata.py"; Desc="Loading test metadata"},
    @{Name="06_load_structure.py"; Desc="Loading test structure"}
)

foreach ($script in $scripts) {
    Write-Host "Running: $($script.Desc)" -ForegroundColor Yellow
    $scriptPath = "deterministic\$($script.Name)"
    
    if (Test-Path $scriptPath) {
        $result = python $scriptPath 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  ✅ $($script.Desc) - Success" -ForegroundColor Green
        } else {
            Write-Host "  ❌ $($script.Desc) - Failed (exit code: $LASTEXITCODE)" -ForegroundColor Red
            Write-Host $result -ForegroundColor Red
        }
    } else {
        Write-Host "  ⚠️ Script not found: $scriptPath" -ForegroundColor Yellow
    }
    Write-Host ""
}

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Data Loading Complete" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
