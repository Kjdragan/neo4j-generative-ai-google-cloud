# Neo4j Generative AI with Google Cloud (Updated)

## 🔥 Now with Gemini 2.5 Pro Preview Support!

This project demonstrates how to use Google Cloud's Vertex AI Gemini models with Neo4j to build and query a knowledge graph. The modernized implementation uses the latest **Gemini 2.5 Pro Preview** models for all LLM tasks and the latest Gemini embedding models for vector search capabilities, powered by the new **Google GenAI SDK**.

The dataset comes from the SEC's EDGAR system, specifically Form-13 filings, which were downloaded using [these scripts](https://github.com/neo4j-partners/neo4j-sec-edgar-form13).

The dataflow in this demo consists of two parts:
1. **Ingestion** - We process EDGAR files with Google Cloud Vertex AI Gemini models, extracting entities and relationships which are then ingested into a Neo4j AuraDB instance
2. **Consumption** - Users interact with a modern chat UI built with Streamlit. Natural language queries are converted to Neo4j Cypher using Gemini Pro 2.5, allowing non-technical users to query the knowledge graph

## Project Structure

The project has been modernized with a Python-based implementation that replaces the previous notebooks:

```
/assetmanager
  /src                      # Source code directory
    /api                    # API endpoints for integration
    /data_processing        # Data processing modules
    /models                 # Model implementations
    /ui                     # Streamlit UI components
    /utils                  # Utility modules
    main.py                 # Main entry point
  pyproject.toml           # Project dependencies
  README.md                # This file
/setup_gcp_project.ps1     # GCP project bootstrap script
```

Once that has started, open the notebook and a terminal window within that.
Clone this repo with the command:

    git clone https://github.com/neo4j-partners/neo4j-generative-ai-google-cloud.git

Feedback submitted Generating.

## Setting Up Your Environment

### 1. Bootstrap a New GCP Project

We've created a comprehensive PowerShell script to set up a new GCP project with all the necessary APIs, permissions, and resources:

```powershell
# Run from PowerShell
./setup_gcp_project.ps1 -projectId "your-project-id" -billingAccountId "your-billing-account-id" -region "us-central1"
```

This script will:
- Create a new GCP project
- Link your billing account
- Enable required APIs (Vertex AI, Compute Engine, Cloud Storage, etc.)
- Create service accounts with appropriate roles
- Create a Cloud Storage bucket for data
- Set up Secret Manager for Neo4j credentials
- Configure firewall rules for HTTP access

### 2. Neo4j AuraDB Setup

This demo requires a Neo4j instance. We recommend using Neo4j AuraDB:

1. Sign up for [Neo4j AuraDB](https://console.neo4j.io/)
2. Create a new database instance (Professional or Enterprise tier recommended)
3. Save your connection details (URI, username, password)
4. Add these credentials to your environment (see Configuration section below)

### 3. Enable Vertex AI API and Models

The bootstrap script enables the required APIs, but ensure you have access to these models:
- Gemini-2.5-pro-preview-05-06 (latest Gemini 2.5 Pro Preview)
- Text-embedding-004 (latest Gemini embedding model)

Note: You may need to request access to the Gemini 2.5 Pro Preview models in your GCP project.

## Configuration

Create a `.env` file in the `assetmanager` directory with the following environment variables:

```env
# GCP Settings
GCP_PROJECT_ID=your-project-id
GCP_LOCATION=us-central1
GCP_BUCKET_NAME=your-bucket-name

# Model Settings
LLM_MODEL=gemini-2.5-pro-preview-05-06
EMBEDDING_MODEL=text-embedding-004

# GenAI SDK Settings (Optional)
GOOGLE_GENAI_USE_VERTEXAI=True

# Neo4j Settings
NEO4J_URI=neo4j+s://your-instance-id.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password
NEO4J_DATABASE=neo4j
```

## Installation

We use `uv` for package management. To install the project:

```bash
# Clone the repository
git clone https://github.com/neo4j-partners/neo4j-generative-ai-google-cloud.git
cd neo4j-generative-ai-google-cloud/assetmanager

# Install dependencies using our installation script
./install_dependencies.ps1

# Or use pyproject.toml directly
uv add -r pyproject.toml
```

## Usage

The application provides several commands to process data, generate embeddings, and run the UI:

### 1. Processing Form-13 Filings

```bash
uv run python -m src.main process-form13 --input-dir /path/to/filings --output-dir /path/to/output
```

### 2. Processing Form-10K Filings and Generating Embeddings

```bash
# Download filings
uv run python -m src.main download-form10k --target-dir /path/to/download

# Process filings and generate embeddings
uv run python -m src.main process-form10k --input-dir /path/to/form10k --output-file embeddings.csv

# Upload embeddings to GCS (optional)
uv run python -m src.main upload-embeddings --file embeddings.csv --bucket your-bucket-name
```

### 3. Running the Streamlit UI

```bash
uv run python -m src.main ui --port 8501
```

### 4. Running the API Server (Optional)

```bash
uv run python -m src.main api --host 0.0.0.0 --port 8000
```

## Deployment Options

### Option 1: Local Development

For local development:

```bash
uv run python -m src.main ui --port 8501
```

This will start the Streamlit UI on port 8501, accessible at http://localhost:8501.

### Option 2: Google Compute Engine VM

1. Create a VM instance:

```bash
gcloud compute instances create neo4j-gemini-app \
    --image-project debian-cloud \
    --image-family debian-12 \
    --zone="us-central1-a" \
    --tags=http-server \
    --scopes=cloud-platform
```

2. SSH into the VM and install required software:

```bash
gcloud compute ssh --zone "us-central1-a" neo4j-gemini-app

# Install required packages
sudo apt update
sudo apt install -y git python3 python3-pip python3-venv

# Clone the repository
git clone https://github.com/neo4j-partners/neo4j-generative-ai-google-cloud.git
cd neo4j-generative-ai-google-cloud

# Install uv package manager
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.cargo/bin:$PATH"

# Install dependencies and run the application
cd assetmanager
uv add -r pyproject.toml

# Create .env file (see Configuration section)
nano .env

# Run the application
uv run python -m src.main ui --port 8080
```

3. Create a firewall rule to allow HTTP traffic (if not already done by the bootstrap script):

```bash
gcloud compute firewall-rules create allow-http \
    --allow tcp:8080 \
    --target-tags=http-server \
    --description="Allow HTTP traffic"
```

### Option 3: Cloud Run (Serverless)

For a serverless deployment, you can use Google Cloud Run:

1. Create a `Dockerfile` in the root directory:

```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY assetmanager/ ./

RUN pip install --no-cache-dir uv && \
    uv add -r pyproject.toml

CMD ["python", "-m", "src.main", "ui", "--port", "8080", "--server.address=0.0.0.0"]
```

2. Build and deploy to Cloud Run:

```bash
# Build the container
gcloud builds submit --tag gcr.io/your-project-id/neo4j-generative-ai-app

# Deploy to Cloud Run
gcloud run deploy neo4j-generative-ai-app \
    --image gcr.io/your-project-id/neo4j-generative-ai-app \
    --platform managed \
    --region us-central1 \
    --allow-unauthenticated
```

## Architecture

The modernized application uses the following architecture:

1. **Data Processing**:
   - Entity extraction from SEC EDGAR Form-13 filings using Gemini Pro 2.5
   - Text embedding generation using Gemini text-embedding-004 model
   - Data import into Neo4j AuraDB

2. **Knowledge Graph Querying**:
   - Natural language to Cypher conversion using Gemini Pro 2.5
   - Neo4j Cypher query execution
   - Result visualization in Streamlit UI

## Upgrade to Gemini 2.5 Pro Preview

This project now uses Google's latest Gemini 2.5 Pro Preview model and the new Google GenAI SDK. For details on the upgrade and new capabilities, see [GEMINI_25_UPGRADE.md](./GEMINI_25_UPGRADE.md).

Key improvements include:
- Enhanced reasoning and context understanding
- System instructions for better control of model behavior
- Structured output in JSON format
- Improved multimodal capabilities
- Unified SDK for both Vertex AI and API key authentication

## Additional Resources

- [Neo4j AuraDB Documentation](https://neo4j.com/docs/aura/auradb/)
- [Google Cloud Vertex AI Documentation](https://cloud.google.com/vertex-ai/docs)
- [Google GenAI SDK Documentation](https://ai.google.dev/python/)
- [Gemini 2.5 Pro Preview Documentation](https://cloud.google.com/vertex-ai/docs/generative-ai/model-reference/gemini)
