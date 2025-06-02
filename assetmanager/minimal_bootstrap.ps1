# Ultra-minimal version to identify the specific syntax issue
$envFile = Join-Path $PSScriptRoot ".env"
if (-not (Test-Path $envFile)) {
    Write-Host "Critical: .env file not found!" -ForegroundColor Red
    exit 1
}
Write-Host ".env file found." -ForegroundColor Green

# Define a simple function
function Get-Value {
    param (
        [string]$name
    )
    return $name
}

# Try to use the function
$value = Get-Value -name "test"
$project_id = "neo4j-deployment-new1"

# Test if condition
if ($value -eq "test") {
    Write-Host "Value is test" -ForegroundColor Green
} 
else {
    Write-Host "Value is not test" -ForegroundColor Yellow
}

Write-Host "Project ID: $project_id" -ForegroundColor Green
Write-Host "Verification completed successfully." -ForegroundColor Green
