# Installation script for Neo4j Asset Manager with Gemini 2.5 Pro Preview
# Uses uv for Python package management

# Ensure we're in the right directory
cd $PSScriptRoot

Write-Host "Installing dependencies with uv..." -ForegroundColor Green

# Install main dependencies
uv add google-genai>=1.18.0
uv add google-cloud-aiplatform>=1.44.0
uv add google-api-python-client>=2.122.0
uv add google-cloud-core>=2.4.1
uv add google-cloud-storage>=2.7.0
uv add neo4j>=5.13.0
uv add graphdatascience
uv add retry==0.9.2
uv add pydantic>=2.5.0
uv add streamlit>=1.27.2
uv add streamlit-chat>=0.1.1
uv add streamlit-chat-media>=0.0.4
uv add numpy
uv add pandas
uv add requests
uv add plotly>=5.20.0
uv add tqdm
uv add pillow
uv add altair\<5
uv add python-dotenv
uv add fastapi>=0.104.0
uv add uvicorn>=0.24.0

# Install dev dependencies
uv add --dev pytest>=7.4.0
uv add --dev pytest-cov>=4.1.0
uv add --dev pytest-mock>=3.12.0
uv add --dev black>=23.7.0
uv add --dev isort>=5.12.0
uv add --dev mypy>=1.5.1
uv add --dev ruff>=0.1.0

Write-Host "Dependencies installed successfully!" -ForegroundColor Green
Write-Host "You can now run the application with 'uv run app.py'" -ForegroundColor Cyan
