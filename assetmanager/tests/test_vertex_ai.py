"""
Tests for the Vertex AI utilities module.
"""
import unittest
from unittest import mock

import pytest
from google.cloud.aiplatform.gapic.schema import predict

from src.utils.vertex_ai import (generate_text, get_text_embedding,
                                init_vertex_ai, process_multimodal)


class TestVertexAI(unittest.TestCase):
    """Test cases for the Vertex AI utilities module."""
    
    @mock.patch("src.utils.vertex_ai.vertexai")
    def test_init_vertex_ai(self, mock_vertexai):
        """Test initializing Vertex AI."""
        project_id = "test-project"
        location = "us-central1"
        
        init_vertex_ai(project_id, location)
        
        mock_vertexai.init.assert_called_once_with(
            project=project_id,
            location=location
        )
    
    @mock.patch("src.utils.vertex_ai.vertexai.GenerativeModel")
    @mock.patch("src.utils.vertex_ai.init_vertex_ai")
    def test_generate_text(self, mock_init, mock_model_class):
        """Test generating text with Gemini."""
        # Setup mock response
        mock_model = mock_model_class.return_value
        mock_response = mock.MagicMock()
        mock_response.text = "Generated text"
        mock_model.generate_content.return_value = mock_response
        
        # Test function
        result = generate_text(
            prompt="Test prompt",
            temperature=0.5,
            max_output_tokens=100,
            model_name="gemini-1.5-pro-001"
        )
        
        # Verify
        mock_init.assert_called_once()
        mock_model_class.assert_called_once_with("gemini-1.5-pro-001")
        mock_model.generate_content.assert_called_once()
        self.assertEqual(result, "Generated text")
    
    @mock.patch("src.utils.vertex_ai.vertexai.preview.TextEmbeddingModel")
    @mock.patch("src.utils.vertex_ai.init_vertex_ai")
    def test_get_text_embedding(self, mock_init, mock_model_class):
        """Test getting text embeddings."""
        # Setup mock response
        mock_model = mock_model_class.return_value
        mock_response = mock.MagicMock()
        mock_embedding = [0.1, 0.2, 0.3]
        mock_response.values = [mock_embedding]
        mock_model.get_embeddings.return_value = [mock_response]
        
        # Test function
        result = get_text_embedding(
            text="Test text",
            model_name="text-embedding-004"
        )
        
        # Verify
        mock_init.assert_called_once()
        mock_model_class.assert_called_once_with("text-embedding-004")
        mock_model.get_embeddings.assert_called_once_with(["Test text"])
        self.assertEqual(result, mock_embedding)
    
    @mock.patch("src.utils.vertex_ai.vertexai.GenerativeModel")
    @mock.patch("src.utils.vertex_ai.init_vertex_ai")
    def test_process_multimodal(self, mock_init, mock_model_class):
        """Test processing multimodal content."""
        # Setup mock response
        mock_model = mock_model_class.return_value
        mock_response = mock.MagicMock()
        mock_response.text = "Multimodal response"
        mock_model.generate_content.return_value = mock_response
        
        # Test function
        result = process_multimodal(
            prompt="Test prompt",
            image_path="image.jpg",
            temperature=0.5,
            max_output_tokens=100,
            model_name="gemini-1.5-pro-001"
        )
        
        # Verify
        mock_init.assert_called_once()
        mock_model_class.assert_called_once_with("gemini-1.5-pro-001")
        mock_model.generate_content.assert_called_once()
        self.assertEqual(result, "Multimodal response")


if __name__ == "__main__":
    # This allows running tests with uv
    unittest.main()
