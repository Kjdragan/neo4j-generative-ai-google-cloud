# Neo4j Generative AI Google Cloud

A modern, universal document processing pipeline that leverages the latest GCP services to create comprehensive knowledge graphs in Neo4j.

## Overview

This project builds a document processing pipeline that can handle various document types and extract knowledge to build Neo4j knowledge graphs. It uses Google Cloud Platform services including Document AI, Vertex AI Gemini 2.5, and Cloud Storage, integrated with Neo4j's vector search capabilities.

## Features

- Universal document processing supporting multiple document types
- Document AI integration for intelligent document parsing
- Vertex AI Gemini 2.5 integration for advanced entity extraction
- Semantic text chunking and embedding generation
- Neo4j knowledge graph integration with vector search
- Comprehensive error handling and resilience
- Scalable architecture for production-grade performance

## Getting Started

### Prerequisites

- Python 3.10+
- Access to Google Cloud Platform with the following APIs enabled:
  - Vertex AI (`aiplatform.googleapis.com`)
  - Compute Engine (`compute.googleapis.com`)
  - Cloud Storage (`storage.googleapis.com`)
  - Document AI (`documentai.googleapis.com`)
  - Secret Manager (`secretmanager.googleapis.com`)
  - Identity and Access Management (`iam.googleapis.com`)
  - Cloud Run (`run.googleapis.com`)
- Neo4j Aura database with vector search capabilities
- Service account with appropriate permissions

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/neo4j-generative-ai-google-cloud.git
cd neo4j-generative-ai-google-cloud

# Install dependencies using uv (never use pip)
uv add -r requirements.txt
```

### Configuration

Create a `.env` file in the project root with the following variables:

```
GCP_PROJECT_ID=your-gcp-project-id
GCP_LOCATION=us-central1
VERTEX_PROJECT_ID=your-vertex-project-id
VERTEX_LOCATION=us-central1
LLM_MODEL=gemini-2.5-pro-preview-05-06
NEO4J_URI=neo4j+s://your-neo4j-instance.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password
```

### Verify Bootstrap

Verify that your GCP project is correctly set up:

```bash
uv run python verify_bootstrap.py
```

## Usage

```bash
# Process a document
uv run python -m src.document_pipeline.main --input-file=path/to/document.pdf
```

## Development

```bash
# Run tests
uv run pytest
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.
