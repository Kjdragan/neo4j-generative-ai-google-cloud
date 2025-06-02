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

# Use gsutil to check bucket existence - more reliable than gcloud storage
try {
    # gsutil ls returns exit code 0 if bucket exists and is accessible
    $null = & gsutil ls -b "gs://$bucketName" 2>$null
    $bucketExists = ($LASTEXITCODE -eq 0)
}
catch {
    $bucketExists = $false
}

if ($bucketExists) {
    Write-Host "   Storage bucket gs://$bucketName exists" -ForegroundColor Green
    
    # Get additional bucket information
    $bucketInfo = & gsutil ls -L -b "gs://$bucketName" 2>$null | Where-Object { $_ -match "Location|Storage class" }
    if ($bucketInfo) {
        $bucketInfo | ForEach-Object {
            Write-Host "      $_" -ForegroundColor Cyan
        }
    }
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
Write-Host "`n6. Echoing key .env configurations for Python scripts..." -ForegroundColor Green
$llmModelFromEnv = Get-EnvVariable -variableName "LLM_MODEL"
$thinkingBudgetFromEnv = Get-EnvVariable -variableName "LLM_THINKING_BUDGET"
$neo4jUriFromEnv = Get-EnvVariable -variableName "NEO4J_URI"
Write-Host "   - Expected LLM_MODEL: $($llmModelFromEnv)"
Write-Host "   - Expected LLM_THINKING_BUDGET: $($thinkingBudgetFromEnv)"
if (-not [string]::IsNullOrEmpty($neo4jUriFromEnv)) {
    Write-Host "   - Expected NEO4J_URI (first 20 chars): $($neo4jUriFromEnv.Substring(0, [System.Math]::Min($neo4jUriFromEnv.Length, 20)))..."
} else {
    Write-Host "   - Expected NEO4J_URI: Not set in .env"
}

# Test Vertex AI access and Neo4j Connection using Python
Write-Host "`n7. Testing Vertex AI and Neo4j with Python..." -ForegroundColor Green
Write-Host "   This will run an embedded Python script to test these services."

$testScript = @"
import os
import json
from dotenv import load_dotenv
import google.genai as genai

# Load environment variables from .env in the current directory (assetmanager)
load_dotenv()

# Get environment variables with fallbacks
PROJECT_ID = os.getenv('GCP_PROJECT_ID', 'neo4j-deployment-new1')
NEO4J_URI = os.getenv('NEO4J_URI', '')
NEO4J_USER = os.getenv('NEO4J_USER', 'neo4j')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD', '')
LLM_MODEL = os.getenv('LLM_MODEL', 'gemini-2.5-pro-preview-05-06')  # Using preferred model
LLM_THINKING_BUDGET = int(os.getenv('LLM_THINKING_BUDGET', 1024))

print(f"Python: Using GCP_PROJECT_ID: {PROJECT_ID}")

# Vertex AI Test
print("  --- Vertex AI Test --- ")
print(f"    Attempting to use LLM Model: {LLM_MODEL}")
print(f"    With Thinking Budget: {LLM_THINKING_BUDGET}")

try:
    # Initialize Vertex AI client according to google-genai SDK
    client = genai.Client(project=PROJECT_ID, location='us-central1', vertexai=True)
    
    # Set up generation parameters as a simple dictionary
    generation_params = {
        'temperature': 0.1,
        'max_output_tokens': 1024
    }
    
    # Quick test of LLM with proper API format
    prompt = "Hello, are you operational?"
    response = client.generate_content(
        model=LLM_MODEL,
        contents=prompt,
        **generation_params  # Pass parameters directly
    )
    
    # Print response
    print("    Vertex AI Test Success: Model responded with:")
    print(f"    {response.text[:100]}...")
    
except Exception as e:
    print(f"    Vertex AI Test ERROR: {str(e)}")

# Neo4j Connection Test
print("  --- Neo4j Connection Test --- ")

# Validate NEO4J_URI - ensure it's not empty and has a valid scheme
if not NEO4J_URI or '://' not in NEO4J_URI:
    print(f"    Neo4j Connection ERROR: Invalid URI format. URI should include a scheme like 'neo4j://', 'bolt://' or 'neo4j+s://'")
    raise ValueError("Invalid Neo4j URI")

# Only show first 20 chars of URI for security
uri_display = NEO4J_URI[:20] + '...' if len(NEO4J_URI) > 20 else NEO4J_URI
print(f"    Attempting to connect to Neo4j at {uri_display} (credentials hidden)")

try:
    # Try to connect to Neo4j
    import neo4j
    driver = neo4j.GraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USER, NEO4J_PASSWORD)
    )
    # Test connection with simple query
    with driver.session() as session:
        # Simple query to test connection
        result = session.run("RETURN 'Connected to Neo4j!' as message")
        message = result.single()["message"]
        print(f"    Neo4j Test Success: {message}")
        # Check for Vertex AI Vector Index
        try:
            vector_result = session.run("SHOW INDEXES YIELD name, type WHERE type='VECTOR' RETURN name")
            vector_indexes = [record["name"] for record in vector_result]
            
            if vector_indexes:
                print(f"    Found {len(vector_indexes)} vector indexes: {', '.join(vector_indexes)}")
            else:
                print("    No vector indexes found. You may need to create one for embedding search.")
        except Exception as vector_err:
            print(f"    Could not check for vector indexes: {vector_err}")
    driver.close()
except Exception as e:
    print(f"   Neo4j Connection ERROR: {e}")

"@

# Save the test script - ensure UTF-8 no BOM encoding for Python compatibility
$testScript | Out-File -FilePath "test_vertex_ai.py" -Encoding utf8NoBOM

# Run the test script using uv for proper dependency management
Write-Host "   Running Vertex AI test script..."
$testResult = & uv run python test_vertex_ai.py
Remove-Item "test_vertex_ai.py"

try {
    $result = $testResult | ConvertFrom-Json
    
    if ($result.success) {
        Write-Host "   ✅ Successfully connected to Vertex AI" -ForegroundColor Green
        Write-Host "      Found $($result.models_found) models" -ForegroundColor Green
        
        if ($result.gemini_models.Count -gt 0) {
            Write-Host "      Gemini models available:" -ForegroundColor Green
            foreach ($model in $result.gemini_models) {
                Write-Host "        - $model" -ForegroundColor Green
            }
        } else {
            Write-Host "      ⚠️ No Gemini models found in your project" -ForegroundColor Yellow
            Write-Host "         Request access to Gemini models in your GCP console" -ForegroundColor Yellow
        }
        
        if ($result.test_generation) {
            Write-Host "      Test generation successful: '$($result.test_generation)'" -ForegroundColor Green
        } elseif ($result.test_generation_error) {
            Write-Host "      ⚠️ Test generation failed: $($result.test_generation_error)" -ForegroundColor Yellow
        }
    } else {
        Write-Host "   ❌ Failed to connect to Vertex AI: $($result.error)" -ForegroundColor Red
    }
} catch {
    Write-Host "   ❌ Failed to parse test results: $_" -ForegroundColor Red
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
}

# Run full verification script
Write-Host "`n8. Running comprehensive verification script..." -ForegroundColor Green

# Save the Python script to a file and run it with uv run python
$testFilePath = "verify_setup.py"
$testScript | Out-File -FilePath $testFilePath -Encoding utf8NoBOM
Write-Host "   Saved test script to $testFilePath"

try {
    Write-Host "   Running Python verification script..."
    & uv run python $testFilePath
    Write-Host "   Python verification script completed." -ForegroundColor Green
} catch {
    Write-Host "   Failed to run Python verification script: $_" -ForegroundColor Red
    Write-Host "      Make sure Python is installed and required packages are available (python-dotenv, google-genai, neo4j)" -ForegroundColor Yellow
}

Write-Host "`nBootstrap verification complete!" -ForegroundColor Green
Write-Host "If any issues were identified, fix them and run this test again." -ForegroundColor Cyan
Write-Host "`nNext step: Deploy your application by following the DEPLOYMENT_GUIDE.md" -ForegroundColor Cyan
