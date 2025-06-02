"""
Configuration module for the Neo4j Asset Manager application.
Handles loading environment variables and settings.
"""
import os
from pathlib import Path
from typing import Dict, Optional

from dotenv import load_dotenv

# Load environment variables from .env file if it exists
env_path = Path(__file__).parent.parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

# GCP Settings
GCP_PROJECT_ID_FROM_ENV = os.getenv("GCP_PROJECT_ID")
GCP_PROJECT = GCP_PROJECT_ID_FROM_ENV if GCP_PROJECT_ID_FROM_ENV else "neo4j-deployment-new1" # Fallback, though .env should provide it
GCP_LOCATION = os.getenv("GCP_LOCATION", "us-central1")

# Model Settings - Using latest Gemini models as requested
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-2.5-flash-preview-05-20")  # Default to Gemini 2.5 Flash
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-004")  # Latest Gemini embedding model
LLM_THINKING_BUDGET = int(os.getenv("LLM_THINKING_BUDGET", "1024")) # Default thinking budget

# GenAI SDK settings
GOOGLE_GENAI_USE_VERTEXAI = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "True").lower() in ["true", "1", "yes"]  
MULTIMODAL_MODEL = os.getenv("MULTIMODAL_MODEL", "gemini-1.5-pro-001")  # Using Gemini for multimodal
MULTIMODAL_MODEL_LOCATION = os.getenv("MULTIMODAL_MODEL_LOCATION", GCP_LOCATION)

# Neo4j Settings (credentials loaded in get_neo4j_credentials)

# Application Settings
APP_NAME = "Neo4j Asset Manager"
APP_VERSION = "1.0.0"
DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")

# Data Storage Settings
DATA_DIR = Path(__file__).parent.parent.parent / "data"
BUCKET_NAME = os.getenv("GCP_BUCKET_NAME", f"{GCP_PROJECT.lower()}-data") # Prefer GCP_BUCKET_NAME from .env if set


def get_neo4j_credentials() -> Dict[str, str]:
    """Return Neo4j credentials as a dictionary, loading from .env."""
    # Ensure .env is loaded if this module is imported elsewhere before a main script's load_dotenv
    env_path_local = Path(__file__).parent.parent.parent / ".env"
    if env_path_local.exists():
        load_dotenv(env_path_local, override=True)

    return {
        "uri": os.getenv("NEO4J_URI", "neo4j+s://1ed0ff88.databases.neo4j.io"),
        "user": os.getenv("NEO4J_USER", "neo4j"),
        "password": os.getenv("NEO4J_PASSWORD", "dIO6cjhYu_oYm0nHgt_ZzpjzSQr19T2qBNbkW-SrOik"),
        "database": os.getenv("NEO4J_DATABASE", "neo4j"),
    }


def get_gcp_settings() -> Dict[str, str]:
    """Return GCP settings as a dictionary."""
    return {
        "project": GCP_PROJECT,
        "location": GCP_LOCATION,
        "llm_model": LLM_MODEL,
        "embedding_model": EMBEDDING_MODEL,
        "llm_thinking_budget": LLM_THINKING_BUDGET,
        "multimodal_model": MULTIMODAL_MODEL,
        "multimodal_model_location": MULTIMODAL_MODEL_LOCATION,
        "bucket_name": BUCKET_NAME,
    }


def validate_config() -> Optional[str]:
    """
    Validate that all required configuration is present.
    
    Returns:
        Optional[str]: Error message if configuration is invalid, None if valid
    """
    required_vars = [
        ("GCP_PROJECT", GCP_PROJECT),
        ("NEO4J_URI", NEO4J_URI),
        ("NEO4J_USER", NEO4J_USER),
        ("NEO4J_PASSWORD", NEO4J_PASSWORD),
    ]
    
    missing = [name for name, value in required_vars if not value]
    
    if missing:
        return f"Missing required configuration: {', '.join(missing)}"
    
    return None
