"""
Tests for the configuration module.
"""
import os
from unittest import TestCase, mock

import pytest

from src.utils.config import (get_gcp_settings, get_neo4j_credentials,
                             init_config, validate_settings)


class TestConfig(TestCase):
    """Test cases for the configuration module."""
    
    @mock.patch.dict(os.environ, {
        "GCP_PROJECT_ID": "test-project", 
        "GCP_LOCATION": "us-central1",
        "GCP_BUCKET_NAME": "test-bucket",
        "LLM_MODEL": "gemini-1.5-pro-001",
        "EMBEDDING_MODEL": "text-embedding-004",
        "NEO4J_URI": "neo4j+s://test.databases.neo4j.io",
        "NEO4J_USER": "neo4j",
        "NEO4J_PASSWORD": "password",
        "NEO4J_DATABASE": "neo4j"
    })
    def test_get_gcp_settings(self):
        """Test getting GCP settings."""
        init_config()
        settings = get_gcp_settings()
        
        self.assertEqual(settings["project"], "test-project")
        self.assertEqual(settings["location"], "us-central1")
        self.assertEqual(settings["bucket"], "test-bucket")
        self.assertEqual(settings["llm_model"], "gemini-1.5-pro-001")
        self.assertEqual(settings["embedding_model"], "text-embedding-004")
    
    @mock.patch.dict(os.environ, {
        "NEO4J_URI": "neo4j+s://test.databases.neo4j.io",
        "NEO4J_USER": "neo4j",
        "NEO4J_PASSWORD": "password",
        "NEO4J_DATABASE": "neo4j"
    })
    def test_get_neo4j_credentials(self):
        """Test getting Neo4j credentials."""
        init_config()
        credentials = get_neo4j_credentials()
        
        self.assertEqual(credentials["uri"], "neo4j+s://test.databases.neo4j.io")
        self.assertEqual(credentials["user"], "neo4j")
        self.assertEqual(credentials["password"], "password")
        self.assertEqual(credentials["database"], "neo4j")
    
    @mock.patch.dict(os.environ, {
        "GCP_PROJECT_ID": "test-project", 
        "GCP_LOCATION": "us-central1",
        "GCP_BUCKET_NAME": "test-bucket",
        "LLM_MODEL": "gemini-1.5-pro-001",
        "EMBEDDING_MODEL": "text-embedding-004",
        "NEO4J_URI": "neo4j+s://test.databases.neo4j.io",
        "NEO4J_USER": "neo4j",
        "NEO4J_PASSWORD": "password",
        "NEO4J_DATABASE": "neo4j"
    })
    def test_validate_settings_success(self):
        """Test successful settings validation."""
        init_config()
        # Should not raise an exception
        validate_settings()
    
    @mock.patch.dict(os.environ, {
        "GCP_PROJECT_ID": "", 
        "GCP_LOCATION": "us-central1",
        "NEO4J_URI": "neo4j+s://test.databases.neo4j.io",
    })
    def test_validate_settings_missing_values(self):
        """Test settings validation with missing values."""
        init_config()
        with pytest.raises(ValueError):
            validate_settings()
    
    @mock.patch.dict(os.environ, {})
    def test_init_config_no_env_file(self):
        """Test initializing config with no .env file."""
        # Should not raise an exception
        init_config(dotenv_path="nonexistent.env")
