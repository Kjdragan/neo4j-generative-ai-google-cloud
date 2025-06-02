# Upgrade script for migrating to Gemini 2.5 Pro Preview with Google GenAI SDK
# This script updates dependencies and environment variables

# Ensure we're in the right directory
cd $PSScriptRoot

Write-Host "🔥 Upgrading to Gemini 2.5 Pro Preview with Google GenAI SDK 🔥" -ForegroundColor Cyan
Write-Host "-------------------------------------------------------------" -ForegroundColor Cyan

# Step 1: Install the new Google GenAI SDK and other dependencies
Write-Host "Step 1: Installing Google GenAI SDK and dependencies..." -ForegroundColor Green
uv add google-genai>=1.18.0
uv add pydantic>=2.5.0

# Step 2: Update .env file with new model names
Write-Host "`nStep 2: Updating environment variables..." -ForegroundColor Green
$envFile = ".env"
$envExampleFile = ".env.example"

if (Test-Path $envFile) {
    # Read existing .env file
    $envContent = Get-Content $envFile -Raw
    
    # Update model name
    $envContent = $envContent -replace "LLM_MODEL=.*", "LLM_MODEL=gemini-2.5-pro-preview-05-06"
    
    # Add GenAI SDK setting if not exists
    if (-not ($envContent -match "GOOGLE_GENAI_USE_VERTEXAI")) {
        $envContent += "`n# GenAI SDK Settings`nGOOGLE_GENAI_USE_VERTEXAI=True`n"
    }
    
    # Write updated content back
    $envContent | Set-Content $envFile
    
    Write-Host "  Updated .env file with new model name and SDK settings" -ForegroundColor Green
} else {
    Write-Host "  No .env file found. Please create one based on .env.example" -ForegroundColor Yellow
    
    if (Test-Path $envExampleFile) {
        Write-Host "  You can use the provided .env.example as a starting point" -ForegroundColor Yellow
    }
}

# Step 3: Run a verification test
Write-Host "`nStep 3: Running verification test..." -ForegroundColor Green
Write-Host "  This will import the new modules to verify the installation" -ForegroundColor Green

$testScript = @"
try:
    from google import genai
    from src.utils.genai_utils import generate_text, get_text_embedding
    print("Success! Google GenAI SDK and utility modules are properly installed.")
except ImportError as e:
    print(f"Error importing modules: {e}")
"@

$testScript | Out-File -FilePath "verify_upgrade.py" -Encoding utf8
uv run python verify_upgrade.py
Remove-Item "verify_upgrade.py"

# Step 4: Provide next steps
Write-Host "`nUpgrade completed!" -ForegroundColor Cyan
Write-Host "`nNext steps:" -ForegroundColor Green
Write-Host "1. Review the GEMINI_25_UPGRADE.md file for documentation" -ForegroundColor White
Write-Host "2. Try running the demo script: uv run python examples/gemini_25_demo.py" -ForegroundColor White
Write-Host "3. Run the test suite to ensure everything works: uv run python run_tests.py" -ForegroundColor White

Write-Host "`nImportant notes:" -ForegroundColor Yellow
Write-Host "- The new SDK requires proper authentication with Vertex AI" -ForegroundColor White
Write-Host "- Make sure your GCP project has access to Gemini 2.5 Pro Preview models" -ForegroundColor White
Write-Host "- See the documentation for more advanced features and capabilities" -ForegroundColor White
