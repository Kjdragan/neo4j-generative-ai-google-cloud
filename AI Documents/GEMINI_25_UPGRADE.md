# Gemini 2.5 Pro Preview Upgrade Guide

This document outlines the changes made to upgrade the Neo4j Asset Manager to use Google's latest Gemini 2.5 Pro Preview model through the Google GenAI SDK.

## Overview of Changes

The project has been updated to use the latest Google GenAI Python SDK with Gemini 2.5 Pro Preview, offering several advantages:

- **Enhanced Model Capabilities**: Gemini 2.5 Pro Preview provides improved reasoning, context understanding, and response quality
- **Unified SDK**: The new Google GenAI SDK (`google-genai`) provides a unified interface for both Vertex AI and direct API usage
- **Improved Features**: Access to advanced features like structured content generation, system instructions, and improved embedding generation
- **Simplified Authentication**: More straightforward authentication methods for both Vertex AI and API key approaches

## Implementation Details

### 1. SDK Integration

The project now uses the `google-genai` Python SDK instead of direct Vertex AI client libraries:

```python
from google import genai
```

### 2. Model Names

Updated model names:
- LLM: `gemini-2.5-pro-preview-05-06` (previously `gemini-1.5-pro-001`)
- Embeddings: `text-embedding-004` (unchanged)

### 3. Authentication

Two authentication methods are supported:

#### Vertex AI (Default)
```python
genai.configure(
    vertexai=True,
    project=project_id,
    location=location
)
```

#### API Key (Express Mode)
```python
genai.configure(api_key="YOUR_API_KEY")
```

Environment variables have been updated to support this configuration:
- `GOOGLE_GENAI_USE_VERTEXAI`: Set to "True" to use Vertex AI (default)
- `GOOGLE_CLOUD_PROJECT`: Your GCP project ID
- `GOOGLE_CLOUD_LOCATION`: Your GCP region

### 4. New Capabilities

The upgrade enables several new capabilities:

1. **System Instructions**: Provide high-level guidance to the model
   ```python
   system_instruction = "You are a Neo4j Cypher query generation expert..."
   ```

2. **Structured Output**: Extract structured data in JSON format
   ```python
   response = client.models.generate_content(
       model=model_name,
       contents=prompt,
       response_schema=schema,
       response_mime_type="application/json"
   )
   result = response.json()
   ```

3. **Enhanced Multimodal**: Better processing of text and images together

4. **Thinking Mode**: More detailed reasoning for complex tasks (enabled by default in Gemini 2.5)

## Required Updates for Users

To use the upgraded system:

1. Update dependencies with the provided script:
   ```bash
   # On Windows PowerShell
   .\install_dependencies.ps1
   ```

2. Update your `.env` file with the new model name:
   ```
   LLM_MODEL=gemini-2.5-pro-preview-05-06
   ```

3. Make sure you have the correct GCP permissions:
   - `roles/aiplatform.user` or equivalent
   - Access to Gemini 2.5 Pro Preview in your GCP project (may require allowlisting)

## API Changes

- The main utility functions remain backward compatible but now use the new SDK internally
- Additional parameters for advanced features are available but optional
- For direct SDK usage, refer to the `src/utils/genai_utils.py` module

## Testing

All tests have been updated to work with the new SDK. Run the tests to ensure everything is working correctly:

```bash
uv run python run_tests.py
```
