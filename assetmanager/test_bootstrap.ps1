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
        
        # Check if the service account key file exists
        $saKeyFile = ".\neo4j-genai-sa-key.json"
        $parentSaKeyFile = "..\neo4j-genai-sa-key.json"

        if (Test-Path $saKeyFile) {
            Write-Host "   Service account key file $saKeyFile exists" -ForegroundColor Green
        } elseif (Test-Path $parentSaKeyFile) {
            Write-Host "   Service account key file found in parent directory: $parentSaKeyFile" -ForegroundColor Green
            # Copy the key file to the current directory for the test scripts to use
            Copy-Item -Path $parentSaKeyFile -Destination $saKeyFile -Force
            Write-Host "   Copied service account key to current directory for tests" -ForegroundColor Green
        } else {
            Write-Host "   Service account key file $saKeyFile not found" -ForegroundColor Yellow
            Write-Host "      Create it with:" -ForegroundColor Yellow
            Write-Host "      gcloud iam service-accounts keys create $saKeyFile --iam-account=$serviceAccountEmail --project=$PROJECT_ID" -ForegroundColor Yellow
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

# Extract all needed variables from .env file
$llmModelFromEnv = Get-EnvVariable -variableName "LLM_MODEL"
$thinkingBudgetFromEnv = Get-EnvVariable -variableName "LLM_THINKING_BUDGET"

# Extract Neo4j URI for Python test - make sure to get exactly what's in the .env file
$neo4jUriFromEnv = Get-EnvVariable -variableName "NEO4J_URI"
$neo4jUser = Get-EnvVariable -variableName "NEO4J_USER"
$neo4jPassword = Get-EnvVariable -variableName "NEO4J_PASSWORD"

# Double check that the NEO4J_URI from .env actually has the prefix
if($neo4jUriFromEnv -and (-not $neo4jUriFromEnv.Contains('://')) -and $neo4jUriFromEnv.Contains('databases.neo4j.io')) {
    Write-Host "   Adding missing 'neo4j+s://' prefix to Neo4j URI in script" -ForegroundColor Yellow
    $neo4jUriFromEnv = "neo4j+s://" + $neo4jUriFromEnv
}
Write-Host "   - Expected LLM_MODEL: $($llmModelFromEnv)"
Write-Host "   - Expected LLM_THINKING_BUDGET: $($thinkingBudgetFromEnv)"
if (-not [string]::IsNullOrEmpty($neo4jUriFromEnv)) {
    Write-Host "   - Expected NEO4J_URI (first 20 chars): $($neo4jUriFromEnv.Substring(0, [System.Math]::Min($neo4jUriFromEnv.Length, 20)))..."
} else {
    Write-Host "   - Expected NEO4J_URI: Not set in .env"
}

# Test Vertex AI access and Neo4j Connection using Python
Write-Host "
7. Testing Vertex AI and Neo4j with Python..." -ForegroundColor Green
Write-Host "   This will run separate Python scripts to test these services."

# Run the Vertex AI test script
Write-Host "   Running Vertex AI test script..." -ForegroundColor Cyan
$output = & uv run python test_vertex_ai.py 2>&1

# Try to parse the output as JSON
try {
    $jsonLine = $output | Where-Object { $_ -match '^\{.*\}$' } | Select-Object -Last 1
    if ($jsonLine) {
        $jsonOutput = $jsonLine | ConvertFrom-Json
        if ($jsonOutput.success) {
            Write-Host "   ✅ Connected to Vertex AI: $($jsonOutput.message)" -ForegroundColor Green
        } else {
            Write-Host "   ❌ Failed to connect to Vertex AI: $($jsonOutput.message)" -ForegroundColor Red
        }
    } else {
        Write-Host "   ❌ No JSON output found from Vertex AI test" -ForegroundColor Red
        Write-Host "   Raw output: $output" -ForegroundColor Yellow
    }
} catch {
    Write-Host "   ❌ Failed to parse Vertex AI test results: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "   Raw output: $output" -ForegroundColor Yellow
}

# Run the Neo4j connection test script
Write-Host "
   Running Neo4j connection test script..." -ForegroundColor Cyan
$output = & uv run python test_neo4j_connection.py 2>&1

# Try to parse the output as JSON
try {
    $jsonLine = $output | Where-Object { $_ -match '^\{.*\}$' } | Select-Object -Last 1
    if ($jsonLine) {
        $jsonOutput = $jsonLine | ConvertFrom-Json
        if ($jsonOutput.success) {
            Write-Host "   ✅ Connected to Neo4j: $($jsonOutput.message)" -ForegroundColor Green
            if ($jsonOutput.vector_indexes -and $jsonOutput.vector_indexes.Count -gt 0) {
                Write-Host "   ✅ Found vector indexes: $($jsonOutput.vector_indexes -join ', ')" -ForegroundColor Green
            } else {
                Write-Host "   ⚠️ No vector indexes found. You may need to create one for embedding search." -ForegroundColor Yellow
            }
        } else {
            Write-Host "   ❌ Failed to connect to Neo4j: $($jsonOutput.error)" -ForegroundColor Red
            if ($jsonOutput.resolution) {
                Write-Host "      Resolution: $($jsonOutput.resolution)" -ForegroundColor Yellow
            }
        }
    } else {
        Write-Host "   ❌ No JSON output found from Neo4j test" -ForegroundColor Red
        Write-Host "   Raw output: $output" -ForegroundColor Yellow
    }
} catch {
    Write-Host "   ❌ Failed to parse Neo4j test results: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "   Raw output: $output" -ForegroundColor Yellow
}

# Done with Vertex AI and Neo4j tests - all testing is now handled by the standalone scripts

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

# Run comprehensive verification by using our standalone test scripts
Write-Host "`n8. Running comprehensive verification..." -ForegroundColor Green

# First verify LLM model in .env file
Write-Host "   Checking LLM model in .env file..." -ForegroundColor Cyan
$envContent = Get-Content .env -ErrorAction SilentlyContinue
$llmModelLine = $envContent | Where-Object { $_ -match '^LLM_MODEL=' }

if ($llmModelLine) {
    $llmModel = $llmModelLine -replace '^LLM_MODEL=', ''
    Write-Host "   LLM model found in .env: $llmModel" -ForegroundColor Green
    
    # Check if it matches our preferred model
    if ($llmModel -eq "gemini-2.5-pro-preview-05-06") {
        Write-Host "   ✅ Using preferred model: gemini-2.5-pro-preview-05-06" -ForegroundColor Green
    } else {
        Write-Host "   ⚠️ Current model ($llmModel) differs from preferred model (gemini-2.5-pro-preview-05-06)" -ForegroundColor Yellow
        Write-Host "      Consider updating LLM_MODEL in .env file for optimal performance" -ForegroundColor Yellow
    }
} else {
    Write-Host "   ❌ LLM_MODEL not found in .env file" -ForegroundColor Red
    Write-Host "      Add LLM_MODEL=gemini-2.5-pro-preview-05-06 to your .env file" -ForegroundColor Yellow
}

# Run final environment verification with our standalone scripts
Write-Host "
   Running final environment verification..." -ForegroundColor Cyan

# Run Vertex AI test one more time to verify
Write-Host "   Verifying Vertex AI connection..." -ForegroundColor Cyan
$output = & uv run python test_vertex_ai.py 2>&1

# Try to parse the output as JSON
try {
    $jsonLine = $output | Where-Object { $_ -match '^\{.*\}$' } | Select-Object -Last 1
    if ($jsonLine) {
        $jsonOutput = $jsonLine | ConvertFrom-Json
        if ($jsonOutput.success) {
            Write-Host "   ✅ Final Vertex AI verification: Success" -ForegroundColor Green
        } else {
            Write-Host "   ❌ Final Vertex AI verification failed: $($jsonOutput.message)" -ForegroundColor Red
        }
    } else {
        Write-Host "   ❌ No JSON output found from final Vertex AI test" -ForegroundColor Red
    }
} catch {
    Write-Host "   ❌ Failed to parse final Vertex AI test results: $($_.Exception.Message)" -ForegroundColor Red
}

# Run Neo4j connection test one more time to verify
Write-Host "   Verifying Neo4j connection..." -ForegroundColor Cyan
$output = & uv run python test_neo4j_connection.py 2>&1

# Try to parse the output as JSON
try {
    $jsonLine = $output | Where-Object { $_ -match '^\{.*\}$' } | Select-Object -Last 1
    if ($jsonLine) {
        $jsonOutput = $jsonLine | ConvertFrom-Json
        if ($jsonOutput.success) {
            Write-Host "   ✅ Final Neo4j verification: Success" -ForegroundColor Green
        } else {
            Write-Host "   ❌ Final Neo4j verification failed: $($jsonOutput.error)" -ForegroundColor Red
        }
    } else {
        Write-Host "   ❌ No JSON output found from final Neo4j test" -ForegroundColor Red
    }
} catch {
    Write-Host "   ❌ Failed to parse final Neo4j test results: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "`nBootstrap verification complete!" -ForegroundColor Green
Write-Host "If any issues were identified, fix them and run this test again." -ForegroundColor Cyan
Write-Host "`nNext step: Deploy your application by following the DEPLOYMENT_GUIDE.md" -ForegroundColor Cyan
