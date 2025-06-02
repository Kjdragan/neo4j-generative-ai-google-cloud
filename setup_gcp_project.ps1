#!/bin/pwsh
# Neo4j Generative AI on Google Cloud - GCP Project Bootstrap Script
# This script sets up a new GCP project with all necessary APIs and permissions
# for running Neo4j Generative AI applications on Google Cloud.

# Configuration variables - Edit these for your project
$PROJECT_ID="neo4j-deployment-new1"  # Fixed project ID as requested
$PROJECT_NAME="Neo4j Generative AI Deployment"
$BILLING_ACCOUNT="014B57-57D99C-19F198"  # Billing account from the image
$PROJECT_OWNER="kevin@clearspringcg.com"
$REGION="us-central1"  # Default region for resources

Write-Host "=== Neo4j Generative AI on GCP Bootstrap Script ===" -ForegroundColor Green
Write-Host "This script will create a new GCP project and enable all required APIs and permissions."
Write-Host "Project ID: $PROJECT_ID"
Write-Host "Project Name: $PROJECT_NAME"
Write-Host "Project Owner: $PROJECT_OWNER"
Write-Host "Billing Account: $BILLING_ACCOUNT"
Write-Host "Region: $REGION"
Write-Host ""

# Function to check if a command exists and install if not
function Check-Command-Install {
    param (
        [string]$Command,
        [string]$InstallMessage
    )
    
    try {
        Get-Command $Command -ErrorAction Stop | Out-Null
        return $true
    }
    catch {
        Write-Host $InstallMessage -ForegroundColor Yellow
        return $false
    }
}

# Check for gcloud CLI
if (-not (Check-Command-Install -Command "gcloud" -InstallMessage "gcloud CLI not found. Please install from https://cloud.google.com/sdk/docs/install")) {
    Write-Host "Please install gcloud CLI and run this script again." -ForegroundColor Red
    exit 1
}

# 1. Create a new GCP project with fixed project ID
Write-Host "Creating new GCP project with ID: $PROJECT_ID..." -ForegroundColor Cyan
gcloud projects create $PROJECT_ID --name="$PROJECT_NAME"

if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to create project. Please check if the project ID 'neo4j-deployment-new' is available or if you have the necessary permissions." -ForegroundColor Red
    exit 1
}
Write-Host "Project created successfully. Project ID: $PROJECT_ID" -ForegroundColor Green

# 2. Link the project to the billing account
Write-Host "Linking project to billing account..." -ForegroundColor Cyan

$billingLinked = $false
$currentBillingAccount = $BILLING_ACCOUNT

for ($i = 0; $i -lt 3; $i++) { # Allow up to 3 attempts
    Write-Host "Attempting to link with Billing Account: $currentBillingAccount"
    $linkOutput = gcloud billing projects link $PROJECT_ID --billing-account=$currentBillingAccount 2>&1
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Successfully linked project $PROJECT_ID to billing account $currentBillingAccount." -ForegroundColor Green
        $billingLinked = $true
        break
    }

    Write-Host "Failed to link billing account $currentBillingAccount." -ForegroundColor Red
    Write-Host "Output: $linkOutput" -ForegroundColor Red

    if ($linkOutput -match "INVALID_ARGUMENT" -or $linkOutput -match "not found") {
        Write-Host "The billing account ID '$currentBillingAccount' might be incorrect or not accessible." -ForegroundColor Yellow
        Write-Host "You can list your available billing accounts with: gcloud billing accounts list" -ForegroundColor Yellow
        $newBillingAccount = Read-Host "Please enter the correct Billing Account ID (or press Enter to skip manual entry for this attempt)"
        if (-not [string]::IsNullOrWhiteSpace($newBillingAccount)) {
            $currentBillingAccount = $newBillingAccount
        } else {
            # If user skips, and it's the first attempt with the script's default, maybe try one more time with the default or just exit loop
            if ($i -eq 0 -and $currentBillingAccount -eq $BILLING_ACCOUNT) {
                 Write-Host "Retrying with the default value from script: $BILLING_ACCOUNT" -ForegroundColor Yellow
            } else {
                 Write-Host "Skipping further attempts for billing account linking due to no new ID provided." -ForegroundColor Yellow
                 break # Exit loop if no new ID is provided after first failure
            }
        }
    } else {
        # For other errors, probably not an ID issue, so don't loop
        Write-Host "An unexpected error occurred. Please check permissions or GCP status." -ForegroundColor Red
        break 
    }
}

if (-not $billingLinked) {
    Write-Host "Could not link project to a billing account after multiple attempts. Exiting." -ForegroundColor Red
    exit 1
}

# 3. Set the project as the current working project
Write-Host "Setting project as current working project..." -ForegroundColor Cyan
gcloud config set project $PROJECT_ID

# 4. Enable required APIs
Write-Host "Enabling required APIs..." -ForegroundColor Cyan
$APIS = @(
    "compute.googleapis.com",            # Compute Engine API
    "aiplatform.googleapis.com",         # Vertex AI API
    "documentai.googleapis.com",       # Document AI API
    "artifactregistry.googleapis.com",   # Artifact Registry API
    "secretmanager.googleapis.com",      # Secret Manager API
    "cloudresourcemanager.googleapis.com", # Resource Manager API
    "iam.googleapis.com",                # IAM API
    "storage.googleapis.com",            # Cloud Storage API
    "run.googleapis.com",                # Cloud Run API
    "container.googleapis.com",          # Kubernetes Engine API
    "serviceusage.googleapis.com",       # Service Usage API
    "iamcredentials.googleapis.com",     # IAM Credentials API
    "cloudapis.googleapis.com",          # Google Cloud APIs
    "cloudbuild.googleapis.com"          # Cloud Build API
)

foreach ($API in $APIS) {
    Write-Host "  Enabling $API..." 
    gcloud services enable $API --project=$PROJECT_ID
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to enable $API. Continuing with other APIs..." -ForegroundColor Yellow
    }
}

# 5. Set up service account for the application
$SERVICE_ACCOUNT_NAME="neo4j-genai-sa"
$SERVICE_ACCOUNT_EMAIL="$SERVICE_ACCOUNT_NAME@$PROJECT_ID.iam.gserviceaccount.com"

Write-Host "Creating service account for application..." -ForegroundColor Cyan
gcloud iam service-accounts create $SERVICE_ACCOUNT_NAME `
    --display-name="Neo4j GenAI Service Account" `
    --project=$PROJECT_ID

if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to create service account. Please check permissions." -ForegroundColor Red
    exit 1
}

# 6. Grant roles to the service account
Write-Host "Granting necessary roles to service account..." -ForegroundColor Cyan
$ROLES = @(
    "roles/aiplatform.admin",             # Full control over AI Platform resources
    "roles/documentai.admin",             # Full control over Document AI resources
    "roles/storage.admin",                # Manage Cloud Storage
    "roles/secretmanager.secretAccessor", # Access secrets
    "roles/run.admin",                    # Manage Cloud Run
    "roles/compute.admin"                 # Manage Compute Engine resources
)

foreach ($ROLE in $ROLES) {
    Write-Host "  Granting $ROLE..." 
    gcloud projects add-iam-policy-binding $PROJECT_ID `
        --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" `
        --role="$ROLE"
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to grant $ROLE. Continuing with other roles..." -ForegroundColor Yellow
    }
}

# 7. Create a key for the service account (optional - for local development)
Write-Host "Creating service account key..." -ForegroundColor Cyan
$KEY_FILE="$PROJECT_ID-$SERVICE_ACCOUNT_NAME-key.json"
gcloud iam service-accounts keys create $KEY_FILE `
    --iam-account=$SERVICE_ACCOUNT_EMAIL

if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to create service account key. Please check permissions." -ForegroundColor Yellow
} else {
    Write-Host "Service account key created: $KEY_FILE" -ForegroundColor Green
    Write-Host "IMPORTANT: Store this key file securely and do not commit it to source control." -ForegroundColor Yellow
}

# 8. Create a Cloud Storage bucket for the application
$BUCKET_NAME="$PROJECT_ID-data"
Write-Host "Creating Cloud Storage bucket: $BUCKET_NAME..." -ForegroundColor Cyan
gcloud storage buckets create gs://$BUCKET_NAME `
    --location=$REGION `
    --project=$PROJECT_ID

if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to create storage bucket. The bucket name might be taken or you don't have sufficient permissions." -ForegroundColor Yellow
}

# 9. Store Neo4j credentials in Secret Manager
Write-Host "Setting up Neo4j credentials in Secret Manager..." -ForegroundColor Cyan
$NEO4J_URI="neo4j+s://1ed0ff88.databases.neo4j.io"
$NEO4J_USER="neo4j"
$NEO4J_PASSWORD="dIO6cjhYu_oYm0nHgt_ZzpjzSQr19T2qBNbkW-SrOik"

# Create secrets
Write-Host "  Creating neo4j-uri secret..."
echo -n "$NEO4J_URI" | gcloud secrets create neo4j-uri --data-file=- --project=$PROJECT_ID

Write-Host "  Creating neo4j-user secret..."
echo -n "$NEO4J_USER" | gcloud secrets create neo4j-user --data-file=- --project=$PROJECT_ID

Write-Host "  Creating neo4j-password secret..."
echo -n "$NEO4J_PASSWORD" | gcloud secrets create neo4j-password --data-file=- --project=$PROJECT_ID

# 10. Set up Vertex AI - Configure access to Gemini models
Write-Host "Setting up Vertex AI access to Gemini models..." -ForegroundColor Cyan
Write-Host "Ensure the following models are accessible in your project:" -ForegroundColor Yellow
Write-Host "  - gemini-2.5-pro-preview-05-06" -ForegroundColor Yellow
Write-Host "  - text-embedding-004" -ForegroundColor Yellow

# 11. Set up firewall rules for VM instances
Write-Host "Creating firewall rule for HTTP access..." -ForegroundColor Cyan
gcloud compute firewall-rules create allow-http `
    --direction=INGRESS `
    --priority=1000 `
    --network=default `
    --action=ALLOW `
    --rules=tcp:80 `
    --source-ranges=0.0.0.0/0 `
    --target-tags=http-server `
    --project=$PROJECT_ID

if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to create firewall rule. Please check permissions." -ForegroundColor Yellow
}

# 12. Summary and next steps
Write-Host ""
Write-Host "=== GCP Project Setup Complete ===" -ForegroundColor Green
Write-Host "Project ID: $PROJECT_ID" -ForegroundColor Green
Write-Host "Service Account: $SERVICE_ACCOUNT_EMAIL" -ForegroundColor Green
Write-Host "Storage Bucket: gs://$BUCKET_NAME" -ForegroundColor Green
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Cyan
Write-Host "1. Run 'gcloud auth application-default login' to set up local authentication" -ForegroundColor Cyan
Write-Host "2. Update the notebook configurations with your project details" -ForegroundColor Cyan
Write-Host "3. Run the Jupyter notebooks to ingest and process data" -ForegroundColor Cyan
Write-Host "4. Deploy the Streamlit UI for querying the data" -ForegroundColor Cyan
Write-Host ""
Write-Host "For more information, refer to the project README.md" -ForegroundColor Cyan
