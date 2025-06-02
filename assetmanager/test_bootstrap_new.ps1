# Neo4j Generative AI Bootstrap Verification Script
# New clean version to avoid syntax issues

# Check for .env file
$envFile = Join-Path $PSScriptRoot ".env"
if (-not (Test-Path $envFile)) {
    Write-Host "❌ Critical: .env file not found in $($PSScriptRoot)!" -ForegroundColor Red
    Write-Host "   Please ensure .env is configured with your GCP_PROJECT_ID, Neo4j credentials, and model settings." -ForegroundColor Yellow
    exit 1
}
Write-Host "   ✅ .env file found." -ForegroundColor Green

# Function to read a value from .env file
function Get-EnvVariable {
    param (
        [string]$variableName
    )
    
    $content = Get-Content $envFile -ErrorAction SilentlyContinue
    $match = $content | Select-String -Pattern "^\s*$($variableName)\s*=\s*(.*)\s*$" -ErrorAction SilentlyContinue
    
    if ($match) {
        return $match.Matches[0].Groups[1].Value.Trim()
    }
    
    return $null
}

Write-Host "🔍 Neo4j Generative AI Bootstrap Verification 🔍" -ForegroundColor Cyan
Write-Host "------------------------------------------------" -ForegroundColor Cyan

# Check project access
$PROJECT_ID_FROM_ENV = Get-EnvVariable -variableName "GCP_PROJECT_ID"
$PROJECT_ID = "neo4j-deployment-new1" # Default value

if ($null -ne $PROJECT_ID_FROM_ENV -and $PROJECT_ID_FROM_ENV -ne "") {
    $PROJECT_ID = $PROJECT_ID_FROM_ENV
    Write-Host "   ℹ️ Using GCP_PROJECT_ID '$PROJECT_ID' from .env file." -ForegroundColor Cyan
} 
else {
    Write-Host "❌ GCP_PROJECT_ID not found in .env file! Using default '$PROJECT_ID'." -ForegroundColor Yellow
}

Write-Host "`n1. Verifying access to GCP Project..." -ForegroundColor Green
Write-Host "   Checking project: $PROJECT_ID"

try {
    $projectInfo = & gcloud projects describe $PROJECT_ID --format="json" | ConvertFrom-Json
    Write-Host "   ✅ Successfully accessed project:" -ForegroundColor Green
    Write-Host "      - Name: $($projectInfo.name)"
    Write-Host "      - Project Number: $($projectInfo.projectNumber)"
    Write-Host "      - Project ID: $($projectInfo.projectId)"
}
catch {
    Write-Host "   ❌ Failed to access GCP project: $PROJECT_ID" -ForegroundColor Red
    Write-Host "      Error: $_" -ForegroundColor Red
    exit 1
}

Write-Host "`nVerification completed successfully." -ForegroundColor Green
