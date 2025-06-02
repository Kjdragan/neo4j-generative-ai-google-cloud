"""
Tests for the Google GenAI utilities module.
"""
import os
import unittest
from unittest.mock import patch, MagicMock

import pytest

from src.utils.genai_utils import (
    init_genai,
    get_client,
    get_text_embedding,
    generate_text,
    process_multimodal,
    extract_structured_data,
    GEMINI_LLM_MODEL,
    GEMINI_EMBEDDING_MODEL,
)

class TestGoogleGenAIUtils(unittest.TestCase):
    """Test cases for Google GenAI utilities."""
    
    def setUp(self):
        """Set up test environment."""
        # Mock environment variables
        self.env_patcher = patch.dict(os.environ, {
            "LLM_MODEL": "gemini-2.5-pro-preview-05-06",
            "EMBEDDING_MODEL": "text-embedding-004",
            "GOOGLE_CLOUD_PROJECT": "test-project",
            "GOOGLE_CLOUD_LOCATION": "us-central1",
            "GOOGLE_GENAI_USE_VERTEXAI": "True",
        })
        self.env_patcher.start()
        
    def tearDown(self):
        """Tear down test environment."""
        self.env_patcher.stop()
    
    @patch("google.genai.configure")
    def test_init_genai(self, mock_configure):
        """Test initialization of Google GenAI SDK."""
        init_genai("test-project", "us-central1")
        mock_configure.assert_called_once_with(
            vertexai=True, 
            project="test-project", 
            location="us-central1"
        )
    
    @patch("google.genai.Client")
    def test_get_client(self, mock_client):
        """Test getting a Google GenAI client."""
        get_client("test-project", "us-central1")
        mock_client.assert_called_once_with(
            vertexai=True, 
            project="test-project", 
            location="us-central1"
        )
    
    @patch("src.utils.genai_utils.get_client")
    def test_get_text_embedding(self, mock_get_client):
        """Test getting text embeddings."""
        # Setup mock client
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        # Setup mock response
        mock_response = MagicMock()
        mock_response.embedding = [0.1, 0.2, 0.3]
        mock_client.models.embed_content.return_value = mock_response
        
        # Call function
        embedding = get_text_embedding(
            "Test text", 
            GEMINI_EMBEDDING_MODEL, 
            "test-project", 
            "us-central1"
        )
        
        # Verify results
        mock_get_client.assert_called_once_with("test-project", "us-central1")
        mock_client.models.embed_content.assert_called_once_with(
            model=GEMINI_EMBEDDING_MODEL,
            content="Test text"
        )
        self.assertEqual(embedding, [0.1, 0.2, 0.3])
    
    @patch("src.utils.genai_utils.get_client")
    def test_generate_text(self, mock_get_client):
        """Test generating text."""
        # Setup mock client
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        # Setup mock response
        mock_response = MagicMock()
        mock_response.text = "Generated text response"
        mock_client.models.generate_content.return_value = mock_response
        
        # Call function
        response = generate_text(
            "Test prompt", 
            0.2, 
            1024, 
            40, 
            0.8, 
            GEMINI_LLM_MODEL, 
            "test-project", 
            "us-central1",
            "System instruction"
        )
        
        # Verify results
        mock_get_client.assert_called_once_with("test-project", "us-central1")
        mock_client.models.generate_content.assert_called_once()
        self.assertEqual(response, "Generated text response")
    
    @patch("src.utils.genai_utils.get_client")
    def test_process_multimodal(self, mock_get_client):
        """Test processing multimodal content."""
        # Setup mock client
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        # Setup mock response
        mock_response = MagicMock()
        mock_response.text = "Multimodal response"
        mock_client.models.generate_content.return_value = mock_response
        
        # Mock the Part.from_file call
        with patch("google.genai.types.Part.from_file") as mock_from_file:
            with patch("google.genai.types.Part.from_text") as mock_from_text:
                # Set up mock parts
                mock_image_part = MagicMock()
                mock_text_part = MagicMock()
                mock_from_file.return_value = mock_image_part
                mock_from_text.return_value = mock_text_part
                
                # Call function
                response = process_multimodal(
                    "Test prompt",
                    "test_image.jpg",
                    0.2,
                    1024,
                    40,
                    0.8,
                    GEMINI_LLM_MODEL,
                    "test-project",
                    "us-central1"
                )
                
                # Verify results
                mock_get_client.assert_called_once_with("test-project", "us-central1")
                mock_from_file.assert_called_once_with("test_image.jpg")
                mock_from_text.assert_called_once_with("Test prompt")
                mock_client.models.generate_content.assert_called_once()
                self.assertEqual(response, "Multimodal response")
    
    @patch("src.utils.genai_utils.get_client")
    def test_extract_structured_data(self, mock_get_client):
        """Test extracting structured data."""
        # Setup mock client
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        # Setup mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {"name": "Test", "value": 123}
        mock_client.models.generate_content.return_value = mock_response
        
        # Call function
        schema = {"type": "object", "properties": {"name": {"type": "string"}, "value": {"type": "integer"}}}
        result = extract_structured_data(
            "Extract name and value from this text: Test has value 123",
            schema,
            0.0,
            2048,
            GEMINI_LLM_MODEL,
            "test-project",
            "us-central1"
        )
        
        # Verify results
        mock_get_client.assert_called_once_with("test-project", "us-central1")
        mock_client.models.generate_content.assert_called_once()
        self.assertEqual(result, {"name": "Test", "value": 123})


if __name__ == '__main__':
    unittest.main()
