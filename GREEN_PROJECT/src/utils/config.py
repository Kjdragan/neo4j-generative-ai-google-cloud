#!/usr/bin/env python
"""
Configuration utilities for the Neo4j Generative AI Google Cloud project.

This module handles loading and accessing configuration settings from environment
variables and other sources.
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv, dotenv_values

# Load environment variables from .env file
env_path = Path(".env")
if env_path.exists():
    # Load directly from file to avoid env var conflicts
    ENV_VARS = dotenv_values(".env")
else:
    # If .env doesn't exist, try to load from environment
    load_dotenv()
    ENV_VARS = {key: os.getenv(key) for key in os.environ}

# GCP Configuration
GCP_PROJECT_ID = ENV_VARS.get("GCP_PROJECT_ID")
GCP_LOCATION = ENV_VARS.get("GCP_LOCATION", "us-central1")

# Vertex AI Configuration
VERTEX_PROJECT_ID = ENV_VARS.get("VERTEX_PROJECT_ID", GCP_PROJECT_ID)
VERTEX_LOCATION = ENV_VARS.get("VERTEX_LOCATION", GCP_LOCATION)
LLM_MODEL = ENV_VARS.get("LLM_MODEL", "gemini-2.5-pro-preview-05-06")
LLM_THINKING_BUDGET = int(ENV_VARS.get("LLM_THINKING_BUDGET", "1024"))

# Neo4j Configuration
NEO4J_URI = ENV_VARS.get("NEO4J_URI", "")
NEO4J_USER = ENV_VARS.get("NEO4J_USER", "")
NEO4J_PASSWORD = ENV_VARS.get("NEO4J_PASSWORD", "")
NEO4J_DATABASE = ENV_VARS.get("NEO4J_DATABASE", "neo4j")

# Document AI Configuration
DOCAI_FORM_PROCESSOR_ID = ENV_VARS.get("DOCAI_FORM_PROCESSOR_ID", "")
DOCAI_OCR_PROCESSOR_ID = ENV_VARS.get("DOCAI_OCR_PROCESSOR_ID", "")
DOCAI_SPLITTER_PROCESSOR_ID = ENV_VARS.get("DOCAI_SPLITTER_PROCESSOR_ID", "")
DOCAI_QUALITY_PROCESSOR_ID = ENV_VARS.get("DOCAI_QUALITY_PROCESSOR_ID", "")

# Storage Configuration
STORAGE_BUCKET = f"{GCP_PROJECT_ID}-data" if GCP_PROJECT_ID else ""

def get_config(key: str, default: Any = None) -> Any:
    """
    Get a configuration value by key.
    
    Args:
        key: The configuration key to look up
        default: Default value if key is not found
        
    Returns:
        The configuration value or default if not found
    """
    return ENV_VARS.get(key, default)

def validate_required_config() -> Dict[str, bool]:
    """
    Validate that all required configuration settings are present.
    
    Returns:
        A dictionary with validation results for each required setting
    """
    validation = {
        "gcp_project_id": bool(GCP_PROJECT_ID),
        "vertex_project_id": bool(VERTEX_PROJECT_ID),
        "neo4j_uri": bool(NEO4J_URI),
        "neo4j_user": bool(NEO4J_USER),
        "neo4j_password": bool(NEO4J_PASSWORD),
    }
    
    return validation

def is_config_valid() -> bool:
    """
    Check if all required configuration settings are valid.
    
    Returns:
        True if all required settings are present, False otherwise
    """
    validation = validate_required_config()
    return all(validation.values())

def get_docai_processor_id(processor_type: str) -> Optional[str]:
    """
    Get the Document AI processor ID for a specific processor type.
    
    Args:
        processor_type: The type of processor ("form", "ocr", "splitter", "quality")
        
    Returns:
        The processor ID or None if not configured
    """
    processor_map = {
        "form": DOCAI_FORM_PROCESSOR_ID,
        "ocr": DOCAI_OCR_PROCESSOR_ID,
        "splitter": DOCAI_SPLITTER_PROCESSOR_ID,
        "quality": DOCAI_QUALITY_PROCESSOR_ID,
    }
    
    return processor_map.get(processor_type.lower())
