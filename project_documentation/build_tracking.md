# Build Tracking Log

## Session Date: 2025-06-02

### Objective: Fixing PowerShell Bootstrap Script and Python SDK Integration

**Key Activities:**

1. **PowerShell Script Structure Fix (`test_bootstrap.ps1`):**
   * Fixed syntax errors in `assetmanager/test_bootstrap.ps1` including proper closing of conditional blocks and code structure.
   * Corrected indentation in embedded Python scripts to ensure they run properly when extracted to temporary files.
   * Updated script to use `utf8NoBOM` encoding for Python script files to prevent encoding issues.

2. **Storage Bucket Verification Enhancement:**
   * Replaced unreliable bucket existence check with more robust `gsutil`-based verification.
   * Added display of bucket metadata (storage class, location) when bucket exists.
   * Improved error handling and output formatting for better troubleshooting.

3. **Google GenAI SDK Update:**
   * Updated embedded Python script to use the correct `google-genai` SDK instead of deprecated `google-generativeai`.
   * Fixed API usage with correct parameter passing for `generate_content` function.
   * Updated initialization method to properly connect to Vertex AI with the correct project settings.

4. **Neo4j Connection Validation:**
   * Added proper URI scheme validation in Neo4j connection test.
   * Improved error reporting with security-conscious URI display (truncating credentials).
   * Added vector index detection for LLM integration verification.

5. **Python Dependency Management:**
   * Updated all Python code to use official `google-genai` package per project standards.
   * Ensured compatibility with the preferred `uv` package manager.
   * Updated inline documentation and error messages to reflect current package requirements.

**Next Steps:**

1. **Complete Service Account Key Setup:**
   * Generate service account key as prompted by the bootstrap script.
   * Store it securely and update `.env` file with proper references.

2. **Run End-to-End Verification:**
   * Re-run the bootstrap script with all fixes to verify complete functionality.
   * Validate both Vertex AI and Neo4j connectivity.
   * Ensure vector indexes are properly detected for embedding search functionality.

3. **Document GCP Configuration:**
   * Update project documentation with complete GCP setup requirements.
   * Create developer guide with common troubleshooting steps for the bootstrap process.

## Session Date: 2025-06-01

### Objective: Modernizing Document Processing Pipeline - Phase 2 (Implementation & Setup)

**Key Activities:**

1.  **Lint Error Fix (`processor.py`):**
    *   Identified and fixed a lint error in `assetmanager/src/document_pipeline/processor.py` where non-default arguments followed default arguments in the `DocumentProcessor.__init__` method.
    *   Reordered parameters to place all required arguments before optional ones.

2.  **Import Management (`processor.py`):**
    *   Reviewed `assetmanager/src/document_pipeline/processor.py` for necessary imports.
    *   Added missing global imports for `json`, `csv`, and `BeautifulSoup` (from `bs4`) to ensure all processing methods have their dependencies available at the top level.

3.  **Dependency Management (`requirements.txt`):**
    *   Checked for an existing `requirements.txt` file.
    *   Created a new `requirements.txt` file in the `assetmanager/` directory.
    *   Added the following core dependencies for the document processing pipeline:
        *   `google-cloud-documentai`
        *   `google-cloud-storage`
        *   `google-generativeai`
        *   `neo4j`
        *   `beautifulsoup4`
        *   `python-dotenv`

4.  **Pipeline Entry Point (`main.py`):**
    *   Created `assetmanager/src/document_pipeline/main.py` to serve as a command-line interface for the document processing pipeline.

5.  **Bootstrap Verification Script (`verify_bootstrap.py`):**
    *   Fixed Vertex AI client initialization to use the modern `google-genai` Python SDK approach with `genai.Client(vertexai=True, project=..., location=...)`.
    *   Simplified model generation call to `client.models.generate_content(model=LLM_MODEL, contents=prompt)` as per the latest official example.
    *   Removed unsupported parameters like `generation_config` that caused runtime errors.
    *   Added robust error handling and logging for model generation.
    *   Enhanced logging functions to handle Unicode encoding errors gracefully.
    *   Fixed GCP CLI command format issues by removing single quotes around format parameters.
    *   Improved service account verification to use list filtering instead of direct describe commands.
    *   Added support for both API key and project-based authentication.
    *   Added proper environment variable handling for Vertex AI-specific variables.
    *   Added detailed bucket metadata logging and Neo4j connection verification.
    *   The script handles environment variable loading (from `.env` in `assetmanager/`), command-line argument parsing (for file path and configuration overrides), `DocumentProcessor` initialization, and invoking the document processing logic.

6.  **Vertex AI Connection Approach:**
    *   **Correct Client Initialization:** The working approach uses `genai.Client(vertexai=True, project=VERTEX_PROJECT_ID, location=VERTEX_LOCATION)` to properly initialize the Vertex AI client.
    *   **Simplified Model Generation:** The correct approach uses `client.models.generate_content(model=LLM_MODEL, contents=prompt)` without any generation_config parameters that caused errors.
    *   **Environment Variables:** The solution requires proper environment variables in `.env` including `VERTEX_PROJECT_ID`, `VERTEX_LOCATION`, and `VERTEX_MODEL_REGION`.
    *   **API Key Handling:** The solution supports both API key authentication (via `GOOGLE_API_KEY`) and project-based authentication through GCP credentials.
    *   **Error Handling:** Added robust error handling for model generation with proper exception catching and logging.

7.  **Neo4j Connection Approach:**
    *   **Direct Environment Variable Loading:** The working approach loads Neo4j connection details directly from `.env` file using `dotenv_values()` instead of relying on environment variables.
    *   **DNS Resolution Check:** Added DNS resolution verification for Neo4j hostname before attempting connection to provide better diagnostics.
    *   **Secure Connection String:** Uses the proper `neo4j+s://` protocol format for secure connections to Neo4j Aura.
    *   **Connection Verification:** Performs a simple RETURN 1 query to verify actual database connectivity beyond just driver initialization.
    *   **Vector Index Check:** Added verification for vector indexes to ensure embedding search readiness.
    *   **Sensitive Information Masking:** Implemented masking of sensitive connection details in logs for security.
    *   Includes basic logging and error handling for common issues like missing configuration or file not found.

**Next Steps (Setup & Initial Test):**

1.  **Install Dependencies:**
    *   Navigate to the `assetmanager/` directory.
    *   Run `uv add <package_name>` for each of the following packages:
        *   `google-cloud-documentai`
        *   `google-cloud-storage`
        *   `google-generativeai`
        *   `neo4j`
        *   `beautifulsoup4`
        *   `python-dotenv`

2.  **Verify `.env` Configuration:**
    *   Ensure `assetmanager/.env` is correctly configured with all necessary credentials and IDs (GCP project, Neo4j connection, DocAI processor ID, GCS bucket, etc.).

3.  **Run the Pipeline (Test):**
    *   From the `assetmanager/` directory, execute the pipeline using a command like:
        ```powershell
        uv run python -m src.document_pipeline.main C:\path\to\your\sample_document.pdf
        ```
    *   Replace the sample path with an actual document path.
    *   Use `uv run python -m src.document_pipeline.main --help` to see all command-line options for overriding configurations.

5.  **GCP Bootstrap Script Update (`setup_gcp_project.ps1`):**
    *   Reviewed the existing `setup_gcp_project.ps1` script.
    *   Added `documentai.googleapis.com` to the list of APIs to be enabled.
    *   Updated service account (`neo4j-genai-sa`) roles for broader permissions:
        *   `roles/aiplatform.admin` (from `roles/aiplatform.user`)
        *   `roles/documentai.admin` (from `roles/documentai.apiUser`)

6.  **SDK and Model Standardization:**
    *   Acknowledged user preference for `google-generativeai` Python SDK.
    *   Updated default LLM model to `gemini-2.5-pro-preview-05-06` in `VertexAIProcessor`, `DocumentProcessor`, and `main.py`.
    *   Created a memory item to retain this preference for future development.

---

### GCP Bootstrap, Configuration, and Verification Learnings (Neo4j GenAI Deployment)

This section summarizes key learnings and troubleshooting steps identified during the setup and verification of the GCP environment for the Neo4j Generative AI deployment on 2025-06-01.

**1. GCP Project Setup & Organization Policies:**

*   **Unique Project ID:** Ensure the `GCP_PROJECT_ID` (e.g., `neo4j-deployment-new1`) is unique and consistently used across all scripts (`setup_gcp_project.ps1`, `delete_gcp_project.ps1`, `test_bootstrap.ps1`) and the `assetmanager/.env` file.
*   **Service Account Key Creation Policy:** The organization policy `constraints/iam.disableServiceAccountKeyCreation` can block the creation of service account keys. This policy must be overridden at the **project level** for the specific GCP project being used. Coordinate with a GCP Organization Administrator to apply this override.
*   **Service Account Key File:** Once the policy is overridden, the service account key (e.g., `gcp_sa_key.json`) can be created (e.g., via GCP Console or `gcloud iam service-accounts keys create`) and should be placed in the `assetmanager/` directory. The `test_bootstrap.ps1` script now specifically checks for `gcp_sa_key.json`.

**2. `.env` Configuration (in `assetmanager/` directory):**

*   This file is the **single source of truth** for critical runtime configurations.
*   **Required Variables:**
    *   `GCP_PROJECT_ID`: Your unique Google Cloud Project ID.
    *   `GCP_BUCKET_NAME`: Storage bucket name (e.g., `your-project-id-data`).
    *   `LLM_MODEL`: Specific generative model to use (e.g., `gemini-2.5-flash-preview-05-20`).
    *   `LLM_THINKING_BUDGET`: Token budget for thinking-enabled models (e.g., `1024`). Set to `0` to disable thinking for compatible models if desired.
    *   `NEO4J_URI`: Full Neo4j connection URI (e.g., `neo4j+s://your-instance.databases.neo4j.io` or `bolt://localhost:7687`).
    *   `NEO4J_USER`: Neo4j username.
    *   `NEO4J_PASSWORD`: Neo4j password.
    *   `NEO4J_DATABASE`: Neo4j database name (usually `neo4j`).
*   **Loading:** The `src/utils/config.py` module is responsible for loading these variables. Ensure `python-dotenv` is listed in `assetmanager/requirements.txt`.

**3. Python SDKs and Environment (`assetmanager/src/utils/`):**

*   **Google GenAI SDK (`google-genai`):**
    *   **Client Initialization (for Vertex AI):** Use `client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)`. Avoid using `genai.configure()` for Vertex AI setup as it can lead to errors.
    *   **Model Configuration:** The active LLM model (e.g., `gemini-2.5-flash-preview-05-20`) and embedding model (`text-embedding-004`) are sourced from `.env` via `config.py` and used in `genai_utils.py`.
    *   **Thinking Budget:** For compatible models like `gemini-2.5-flash-preview-05-20`, the `thinking_budget` is configured in `genai_utils.py` using `types.ThinkingConfig` and `types.GenerationConfig`, with the budget value sourced from `.env` via `config.py`.
*   **Neo4j Connection (`neo4j_utils.py`):** Relies on `NEO4J_URI`, `NEO4J_USER`, and `NEO4J_PASSWORD` from `.env` (loaded via `config.py`). Incorrect or missing values will lead to connection failures.

**4. Hatch Build (`assetmanager/pyproject.toml`):**

*   For successful `uv run hatch build` (or direct Hatch usage) for the `assetmanager` package, ensure the `pyproject.toml` file includes:
    ```toml
    [tool.hatch.build.targets.wheel]
    packages = ["src/neo4j_asset_manager"]
    ```

**5. Bootstrap and Verification Scripts:**

*   **`setup_gcp_project.ps1` (Root Directory):** This script is responsible for initial GCP resource provisioning (project, APIs, service accounts, roles, bucket).
*   **`test_bootstrap.ps1` (`assetmanager/` Directory):**
    *   Run this *after* `setup_gcp_project.ps1` and after configuring `assetmanager/.env` and placing `gcp_sa_key.json`.
    *   It now dynamically reads `GCP_PROJECT_ID` from `.env`.
    *   It checks for the existence of `.env` and `gcp_sa_key.json`.
    *   It echoes key configurations from `.env` (LLM model, thinking budget, Neo4j URI) before running Python tests.
    *   The embedded Python script for testing Vertex AI and Neo4j now:
        *   Uses the correct `genai.Client` initialization.
        *   Loads and uses `LLM_MODEL` and `LLM_THINKING_BUDGET` from environment variables for its test generation.
        *   Prints the Neo4j URI it's attempting to use.
        *   Provides more detailed error messages and tracebacks for easier debugging.

**General Troubleshooting Approach:**

1.  **Start with `.env`:** Double-check all values in `assetmanager/.env` for correctness and completeness.
2.  **Run `test_bootstrap.ps1`:** This script is your primary diagnostic tool after initial setup. Pay close attention to its output, especially the echoed configurations and any Python error messages.
3.  **Check GCP Console:** Verify API enablement, service account existence and permissions, and bucket existence directly in the GCP console if script checks fail.
4.  **Review Organization Policies:** If service account key creation or other IAM operations fail unexpectedly, suspect an organization policy and consult your GCP Organization Admin.


