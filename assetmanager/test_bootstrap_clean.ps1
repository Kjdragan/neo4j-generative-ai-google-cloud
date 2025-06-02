# Test script to verify the bootstrap process worked correctly
# Run this after setup_gcp_project.ps1 to ensure everything is configured properly

# Set the working directory to the script location
Set-Location $PSScriptRoot

# Check for .env file
$envFile = ".env"
if (-not (Test-Path $envFile)) {
    Write-Host "Critical: .env file not found in $($PSScriptRoot)!" -ForegroundColor Red
    Write-Host "Please ensure .env is configured with your GCP_PROJECT_ID, Neo4j credentials, and model settings." -ForegroundColor Yellow
    exit 1
}
Write-Host "   .env file found." -ForegroundColor Green

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

Write-Host "Neo4j Generative AI Bootstrap Verification" -ForegroundColor Cyan
Write-Host "------------------------------------------------" -ForegroundColor Cyan

# Check project access
$PROJECT_ID_FROM_ENV = Get-EnvVariable -variableName "GCP_PROJECT_ID"
$PROJECT_ID = "neo4j-deployment-new1" # Default value

if ($null -ne $PROJECT_ID_FROM_ENV -and $PROJECT_ID_FROM_ENV -ne "") {
    $PROJECT_ID = $PROJECT_ID_FROM_ENV
    Write-Host "   Using GCP_PROJECT_ID '$PROJECT_ID' from .env file." -ForegroundColor Cyan
} 
else {
    Write-Host "GCP_PROJECT_ID not found in .env file! Using default '$PROJECT_ID'." -ForegroundColor Yellow
}

Write-Host "`n1. Verifying access to GCP Project..." -ForegroundColor Green
Write-Host "   Checking project: $PROJECT_ID"

try {
    $projectInfo = & gcloud projects describe $PROJECT_ID --format="json" | ConvertFrom-Json
    Write-Host "   Successfully accessed project:" -ForegroundColor Green
    Write-Host "      - Name: $($projectInfo.name)"
    Write-Host "      - Project Number: $($projectInfo.projectNumber)"
    Write-Host "      - Created: $($projectInfo.createTime)"
} catch {
    Write-Host "   Failed to access project $PROJECT_ID" -ForegroundColor Red
    Write-Host "      Error: $_" -ForegroundColor Red
    Write-Host "      Run 'gcloud auth login' and try again" -ForegroundColor Yellow
    exit 1
}

# Check enabled APIs
Write-Host "`n2. Verifying required APIs are enabled..." -ForegroundColor Green
$requiredApis = @(
    "aiplatform.googleapis.com", 
    "compute.googleapis.com", 
    "storage.googleapis.com",
    "documentai.googleapis.com",
    "secretmanager.googleapis.com",
    "iam.googleapis.com",
    "run.googleapis.com"
)

foreach ($api in $requiredApis) {
    $apiStatus = & gcloud services list --project=$PROJECT_ID --filter="config.name:$api" --format="value(config.name)"
    if ($apiStatus -eq $api) {
        Write-Host "   $api is enabled" -ForegroundColor Green
    } else {
        Write-Host "   $api is not enabled" -ForegroundColor Red
        Write-Host "      Run the bootstrap script again or enable manually:" -ForegroundColor Yellow
        Write-Host "      gcloud services enable $api --project=$PROJECT_ID" -ForegroundColor Yellow
    }
}

# Check storage bucket
Write-Host "`n3. Verifying storage bucket exists..." -ForegroundColor Green
$bucketName = "$PROJECT_ID-data"
$bucketExists = & gcloud storage ls --project=$PROJECT_ID gs://$bucketName 2>$null

if ($bucketExists) {
    Write-Host "   Storage bucket gs://$bucketName exists" -ForegroundColor Green
} else {
    Write-Host "   Storage bucket gs://$bucketName does not exist" -ForegroundColor Red
    Write-Host "      Create it with:" -ForegroundColor Yellow
    Write-Host "      gcloud storage buckets create gs://$bucketName --location=us-central1 --project=$PROJECT_ID" -ForegroundColor Yellow
}

# Check service account
Write-Host "`n4. Verifying service account exists..." -ForegroundColor Green
$serviceAccountName = "neo4j-genai-sa"
$serviceAccountEmail = "$serviceAccountName@$PROJECT_ID.iam.gserviceaccount.com"

try {
    $serviceAccountExists = & gcloud iam service-accounts describe $serviceAccountEmail --project=$PROJECT_ID --format="value(email)" 2>$null
    if ($serviceAccountExists) {
        Write-Host "   Service account $serviceAccountEmail exists" -ForegroundColor Green
        
        # Check for key file
        $keyFilePath = ".\$serviceAccountName-key.json"
        if (Test-Path $keyFilePath) {
            Write-Host "   Service account key file $keyFilePath exists" -ForegroundColor Green
        } else {
            Write-Host "   Service account key file $keyFilePath not found" -ForegroundColor Yellow
            Write-Host "      Create it with:" -ForegroundColor Yellow
            Write-Host "      gcloud iam service-accounts keys create $keyFilePath --iam-account=$serviceAccountEmail --project=$PROJECT_ID" -ForegroundColor Yellow
        }
    } else {
        Write-Host "   Service account $serviceAccountEmail does not exist" -ForegroundColor Red
        Write-Host "      Create it with:" -ForegroundColor Yellow
        Write-Host "      gcloud iam service-accounts create $serviceAccountName --display-name='Neo4j GenAI Service Account' --project=$PROJECT_ID" -ForegroundColor Yellow
    }
} catch {
    Write-Host "   Failed to check service account $serviceAccountEmail" -ForegroundColor Red
    Write-Host "      Error: $_" -ForegroundColor Red
    $serviceAccountExists = $false
}

# Check Service Account IAM Roles
Write-Host "`n5. Verifying Service Account IAM Roles..." -ForegroundColor Green
$requiredRoles = @(
    "roles/aiplatform.admin",
    "roles/documentai.admin",
    "roles/storage.admin",
    "roles/secretmanager.secretAccessor",
    "roles/run.admin",
    "roles/compute.admin"
)

if ($serviceAccountExists) {
    try {
        $policy = & gcloud projects get-iam-policy $PROJECT_ID --format=json | ConvertFrom-Json
        
        foreach ($role in $requiredRoles) {
            $hasRole = $false
            
            foreach ($binding in $policy.bindings) {
                if ($binding.role -eq $role) {
                    $member = "serviceAccount:$serviceAccountEmail"
                    if ($binding.members -contains $member) {
                        $hasRole = $true
                        break
                    }
                }
            }
            
            if ($hasRole) {
                Write-Host "   Role $role is assigned to $serviceAccountEmail" -ForegroundColor Green
            } else {
                Write-Host "   Role $role is NOT assigned to $serviceAccountEmail" -ForegroundColor Yellow
                Write-Host "      Add it with:" -ForegroundColor Yellow
                Write-Host "      gcloud projects add-iam-policy-binding $PROJECT_ID --member=serviceAccount:$serviceAccountEmail --role=$role" -ForegroundColor Yellow
            }
        }
    } catch {
        Write-Host "   Failed to get IAM policy for project $PROJECT_ID" -ForegroundColor Red
        Write-Host "      Error: $_" -ForegroundColor Red
    }
} else {
    Write-Host "   Cannot check roles because service account $serviceAccountEmail does not exist." -ForegroundColor Yellow
}

# Echo key .env variables before Python tests
Write-Host "`n6. Testing Vertex AI and Neo4j connectivity..." -ForegroundColor Green
Write-Host "   Creating test script to validate environment..."

$testScript = @'
import os
import json
from dotenv import load_dotenv
import google.generativeai as genai
from google.genai import types as genai_types # Alias to avoid conflict if neo4j has 'types'

# Load environment variables from .env in the current directory (assetmanager)
load_dotenv()

PROJECT_ID = "{0}" # Injected from PowerShell
LOCATION = "us-central1"

print(f"Python: Using GCP_PROJECT_ID: {PROJECT_ID}")

# Vertex AI Test
print("\n--- Vertex AI Test --- ")
llm_model_name = os.getenv("LLM_MODEL", "gemini-2.5-pro-preview-05-06")
llm_thinking_budget_str = os.getenv("LLM_THINKING_BUDGET", "1024")
llm_thinking_budget = int(llm_thinking_budget_str) if llm_thinking_budget_str.isdigit() else 1024

print(f"   Attempting to use LLM Model: {llm_model_name}")
print(f"   With Thinking Budget: {llm_thinking_budget}")

try:
    client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)
    print(f"   GenAI Client initialized for project: {PROJECT_ID}, location: {LOCATION}")

    # Simple text generation test
    result = {}
    model_list = client.list_models()
    gemini_models = [m.name for m in model_list if "gemini" in m.name]
    
    result["success"] = True
    result["models_found"] = len(model_list)
    result["gemini_models"] = gemini_models
    
    # Try a simple generation if models found
    if gemini_models:
        try:
            response = client.generate_content(
                model=llm_model_name,
                contents="Tell me a very short joke in one sentence.",
                generation_config={"max_output_tokens": 50}
            )
            result["test_generation"] = response.text
        except Exception as gen_error:
            result["test_generation_error"] = str(gen_error)
    
    print(json.dumps(result))

except Exception as e:
    print(json.dumps({"success": False, "error": str(e)}))
    print(f"   Vertex AI Test ERROR: {e}")
    import traceback
    traceback.print_exc()

# Neo4j Connection Test
print("\n--- Neo4j Connection Test --- ")
try:
    from neo4j import GraphDatabase, basic_auth
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")
    database = os.getenv("NEO4J_DATABASE", "neo4j")

    print(f"   Attempting to connect to Neo4j URI (first 30 chars): {uri[:30] if uri else 'Not Set!'}...")

    if not uri or not user or not password:
        missing_vars = []
        if not uri: missing_vars.append("NEO4J_URI")
        if not user: missing_vars.append("NEO4J_USER")
        if not password: missing_vars.append("NEO4J_PASSWORD")
        raise ValueError(f"Missing Neo4j connection details in .env: {', '.join(missing_vars)}")
    
    driver = GraphDatabase.driver(uri, auth=basic_auth(user, password))
    with driver.session(database=database) as session:
        session.run("RETURN 1 AS result")
    driver.close()
    print("   Successfully connected to Neo4j and ran a test query.")
except Exception as e:
    print(f"   Failed to connect to Neo4j: {e}")
    print("      Ensure NEO4J_URI, NEO4J_USER, and NEO4J_PASSWORD are correctly set in .env")
    import traceback
    traceback.print_exc()
'@ -f $PROJECT_ID

# Save the test script - use UTF8 encoding without BOM
$utf8NoBomEncoding = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText("$PSScriptRoot\test_vertex_ai.py", $testScript, $utf8NoBomEncoding)

# Run the test script
Write-Host "   Running Vertex AI test script..."
$testResult = & uv run python test_vertex_ai.py
Remove-Item "$PSScriptRoot\test_vertex_ai.py"

try {
    $result = $testResult | ConvertFrom-Json
    
    if ($result.success) {
        Write-Host "   Successfully connected to Vertex AI" -ForegroundColor Green
        Write-Host "      Found $($result.models_found) models" -ForegroundColor Green
        
        if ($result.gemini_models.Count -gt 0) {
            Write-Host "      Gemini models available:" -ForegroundColor Green
            foreach ($model in $result.gemini_models) {
                Write-Host "        - $model" -ForegroundColor Green
            }
        } else {
            Write-Host "      No Gemini models found in your project" -ForegroundColor Yellow
            Write-Host "         Request access to Gemini models in your GCP console" -ForegroundColor Yellow
        }
        
        if ($result.test_generation) {
            Write-Host "      Test generation successful: '$($result.test_generation)'" -ForegroundColor Green
        } elseif ($result.test_generation_error) {
            Write-Host "      Test generation failed: $($result.test_generation_error)" -ForegroundColor Yellow
        }
    } else {
        Write-Host "   Failed to connect to Vertex AI: $($result.error)" -ForegroundColor Red
    }
} catch {
    Write-Host "   Failed to parse test results: $_" -ForegroundColor Red
    Write-Host "   Raw output: $testResult" -ForegroundColor Red
}

# Create .env file if it doesn't exist
Write-Host "`n7. Checking for .env file..." -ForegroundColor Green
if (-not (Test-Path ".env")) {
    Write-Host "   .env file not found, creating from .env.example" -ForegroundColor Yellow
    
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host "   Created .env file from .env.example" -ForegroundColor Green
    } else {
        Write-Host "   .env.example not found, cannot create .env file" -ForegroundColor Red
    }
} else {
    Write-Host "   .env file exists" -ForegroundColor Green
}

# Run full verification script
Write-Host "`n8. Running comprehensive verification script..." -ForegroundColor Green
if (Test-Path "verify_setup.py") {
    Write-Host "   Running verify_setup.py..."
    & uv run python verify_setup.py
} else {
    Write-Host "   verify_setup.py not found" -ForegroundColor Yellow
}

# Summary
Write-Host "`nBootstrap Verification Complete" -ForegroundColor Cyan
Write-Host "If all checks passed, your environment is ready for deployment!" -ForegroundColor Green
Write-Host "If any checks failed, review the error messages and take corrective action." -ForegroundColor Yellow
Write-Host "`nNext step: Deploy your application by following the DEPLOYMENT_GUIDE.md" -ForegroundColor Cyan
