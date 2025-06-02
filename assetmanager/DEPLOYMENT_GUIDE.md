# Neo4j Asset Manager with Gemini 2.5 Pro Preview - Deployment Guide

This guide walks through the entire process of deploying the Neo4j Asset Manager application with Gemini 2.5 Pro Preview from scratch. Follow these steps in order to ensure a successful deployment.

## Prerequisites

- A Google Cloud Platform account with billing enabled
- Neo4j AuraDB instance (Professional or Enterprise tier recommended)
- PowerShell 7+ (for Windows) or Bash (for Linux/macOS)
- Python 3.10+ with `uv` package manager installed
- Git

## Step 1: Clone the Repository

```bash
git clone https://github.com/neo4j-partners/neo4j-generative-ai-google-cloud.git
cd neo4j-generative-ai-google-cloud
```

## Step 2: Bootstrap Your GCP Project

This critical first step sets up all necessary GCP resources. The bootstrap script is preconfigured to create a project with ID "neo4j-deployment" and use the "KD Billing Account for CS" billing account:

```powershell
# Run from PowerShell
./setup_gcp_project.ps1
```

The script will:
- Create a new GCP project with ID "neo4j-deployment"
- Link it to the "KD Billing Account for CS" billing account
- Enable required APIs (Vertex AI, Cloud Storage, etc.)
- Create service accounts with proper IAM roles
- Configure storage buckets
- Set up networking and firewall rules

## Step 3: Set Up Neo4j AuraDB

1. Sign up for [Neo4j AuraDB](https://console.neo4j.io/)
2. Create a new database instance (Professional or Enterprise tier)
3. Save your connection details (URI, username, password)

## Step 4: Configure Environment Variables

Create a `.env` file in the `assetmanager` directory:

```bash
cd assetmanager
cp .env.example .env
```

Edit the `.env` file with your specific values:
```
# GCP Settings
GCP_PROJECT_ID=your-project-id
GCP_LOCATION=us-central1
GCP_BUCKET_NAME=your-bucket-name

# Model Settings
LLM_MODEL=gemini-2.5-pro-preview-05-06
EMBEDDING_MODEL=text-embedding-004

# GenAI SDK Settings
GOOGLE_GENAI_USE_VERTEXAI=True

# Neo4j Settings
NEO4J_URI=neo4j+s://your-instance-id.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password
NEO4J_DATABASE=neo4j
```

## Step 5: Install Dependencies

Use our installation script which installs all dependencies with `uv`:

```powershell
# Run from the assetmanager directory
./install_dependencies.ps1
```

## Step 6: Verify Your Setup

Run the verification script to ensure everything is configured correctly:

```powershell
# Run from the assetmanager directory
uv run python verify_setup.py
```

This script checks:
- GCP project configuration
- Vertex AI API access
- Neo4j connection
- Access to Gemini 2.5 Pro Preview model

## Step 7: Run the Demo (Optional)

Test the Gemini 2.5 Pro Preview capabilities:

```powershell
uv run python examples/gemini_25_demo.py
```

## Step 8: Deploy the Application

Choose your preferred deployment method:

### Option A: Run Locally

```powershell
uv run python -m src.main ui --port 8501
```

### Option B: Deploy to Google Compute Engine

```powershell
# Deploy using our automated script
uv run python deploy_to_compute_engine.py
```

Or manually:
```powershell
gcloud compute instances create neo4j-gemini-app \
    --image-project debian-cloud \
    --image-family debian-12 \
    --zone="us-central1-a" \
    --tags=http-server \
    --scopes=cloud-platform
```

Follow the remaining deployment steps in the README.md.

### Option C: Deploy to Cloud Run

Create a Dockerfile and deploy as described in the README.md.

## Step 9: Process Data (If Needed)

Load and process SEC filing data:

```powershell
# Process Form-13 filings
uv run python -m src.main process-form13 --input-dir /path/to/filings --output-dir /path/to/output

# Process Form-10K filings and generate embeddings
uv run python -m src.main download-form10k --target-dir /path/to/download
uv run python -m src.main process-form10k --input-dir /path/to/form10k --output-file embeddings.csv
```

## Troubleshooting

### Common Issues

1. **Authentication Issues**: Ensure you're logged in with gcloud:
   ```
   gcloud auth login
   gcloud config set project your-project-id
   ```

2. **Missing API Access**: Request access to Gemini 2.5 Pro Preview model if needed.

3. **Neo4j Connection Errors**: Check firewall settings and credentials.

4. **Dependency Issues**: Try reinstalling dependencies:
   ```
   ./install_dependencies.ps1
   ```

### Getting Help

If you encounter issues:
1. Check the application logs
2. Review the README.md and GEMINI_25_UPGRADE.md
3. File an issue on the GitHub repository
