# Contributing to Neo4j Asset Manager

Thank you for your interest in contributing to Neo4j Asset Manager! This project combines Neo4j graph database with Google Cloud Vertex AI to create intelligent applications for asset management.

## Setting Up Development Environment

1. **Clone the repository**:
   ```bash
   git clone https://github.com/neo4j-partners/neo4j-generative-ai-google-cloud.git
   cd neo4j-generative-ai-google-cloud/assetmanager
   ```

2. **Create a `.env` file**:
   Copy the `.env.example` file to `.env` and fill in your GCP and Neo4j credentials.

3. **Install dependencies with uv**:
   ```bash
   uv add -r pyproject.toml
   uv add --dev
   ```

## Running Tests

Run the tests using the test runner script:

```bash
uv run python run_tests.py
```

For coverage reporting:

```bash
uv run python run_tests.py --coverage
```

## Code Style

This project uses:
- Black for code formatting
- isort for import sorting
- mypy for type checking
- ruff for linting

Format your code before submitting changes:

```bash
uv run black src tests
uv run isort src tests
uv run mypy src
uv run ruff src tests
```

## Project Structure

- `/src` - Source code
  - `/api` - FastAPI endpoints
  - `/data_processing` - Data processing modules
  - `/models` - Core business logic
  - `/ui` - Streamlit UI
  - `/utils` - Utility functions
- `/tests` - Test suite
- `/docs` - Documentation

## Pull Request Process

1. Fork the repository
2. Create a new branch for your feature
3. Add tests for new functionality
4. Ensure all tests pass and code is formatted properly
5. Submit a pull request with a detailed description of changes

## Deployment

Two deployment options are available:
- Google Cloud Run (see `deploy_to_cloud_run.py`)
- Google Compute Engine (see `deploy_to_compute_engine.py`)

## Getting Help

If you have questions, open an issue in the repository or contact the maintainers.

## License

By contributing, you agree that your contributions will be licensed under the project's license.
