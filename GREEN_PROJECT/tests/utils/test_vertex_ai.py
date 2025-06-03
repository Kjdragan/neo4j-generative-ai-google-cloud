#!/usr/bin/env python
"""
Tests for the Vertex AI utility module.

This module contains unit tests for the VertexAIClient class.
"""

import unittest
from unittest import mock
import time

from src.utils.vertex_ai import VertexAIClient
from src.utils import config


class TestVertexAIClient(unittest.TestCase):
    """Test cases for the VertexAIClient class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock the genai.configure method
        self.mock_genai_configure_patcher = mock.patch('google.generativeai.configure')
        self.mock_genai_configure = self.mock_genai_configure_patcher.start()
        
        # Create a VertexAI client with mocked dependencies
        self.vertex_client = VertexAIClient(
            project_id="test-project",
            location="us-central1",
            model_name="gemini-1.5-pro",
            embedding_model="textembedding-gecko@003",
        )
    
    def tearDown(self):
        """Tear down test fixtures."""
        self.mock_genai_configure_patcher.stop()
    
    def test_init(self):
        """Test initialization of VertexAIClient."""
        client = VertexAIClient(
            project_id="test-project",
            location="us-central1",
            model_name="gemini-1.5-pro",
            embedding_model="textembedding-gecko@003",
        )
        
        self.assertEqual(client.project_id, "test-project")
        self.assertEqual(client.location, "us-central1")
        self.assertEqual(client.model_name, "gemini-1.5-pro")
        self.assertEqual(client.embedding_model, "textembedding-gecko@003")
        
        # Verify genai.configure was called with correct arguments
        self.mock_genai_configure.assert_called_once_with(
            project_id="test-project",
            location="us-central1",
        )
    
    def test_init_with_defaults(self):
        """Test initialization of VertexAIClient with default values."""
        # Set up mock config values
        with mock.patch.object(config, 'GCP_PROJECT_ID', "default-project"):
            with mock.patch.object(config, 'VERTEX_LOCATION', "us-west1"):
                with mock.patch.object(config, 'VERTEX_MODEL', "gemini-1.5-flash"):
                    with mock.patch.object(config, 'VERTEX_EMBEDDING_MODEL', "textembedding-gecko@latest"):
                        # Reset mock to clear previous calls
                        self.mock_genai_configure.reset_mock()
                        
                        # Create client with defaults
                        client = VertexAIClient()
                        
                        self.assertEqual(client.project_id, "default-project")
                        self.assertEqual(client.location, "us-west1")
                        self.assertEqual(client.model_name, "gemini-1.5-flash")
                        self.assertEqual(client.embedding_model, "textembedding-gecko@latest")
                        
                        # Verify genai.configure was called with correct arguments
                        self.mock_genai_configure.assert_called_once_with(
                            project_id="default-project",
                            location="us-west1",
                        )
    
    def test_init_missing_required(self):
        """Test initialization with missing required parameters."""
        # Set up mock config values to None
        with mock.patch.object(config, 'GCP_PROJECT_ID', None):
            with mock.patch.object(config, 'VERTEX_LOCATION', None):
                with self.assertRaises(ValueError):
                    VertexAIClient()
    
    def test_exponential_backoff(self):
        """Test exponential backoff calculation."""
        client = self.vertex_client
        
        # Test initial delay
        self.assertEqual(client._exponential_backoff(0), 1.0)
        
        # Test subsequent delays
        self.assertEqual(client._exponential_backoff(1), 2.0)
        self.assertEqual(client._exponential_backoff(2), 4.0)
        
        # Test max delay
        client.max_retry_delay = 3.0
        self.assertEqual(client._exponential_backoff(2), 3.0)
    
    def test_retry_api_call_success(self):
        """Test successful API call with retry."""
        # Mock function that succeeds
        mock_func = mock.Mock(return_value="success")
        
        # Call with retry
        result = self.vertex_client._retry_api_call(mock_func, "arg1", arg2="value2")
        
        # Verify result
        self.assertEqual(result, "success")
        
        # Verify function was called once with correct arguments
        mock_func.assert_called_once_with("arg1", arg2="value2")
    
    def test_retry_api_call_retry_success(self):
        """Test API call that succeeds after retries."""
        # Mock function that fails twice then succeeds
        mock_func = mock.Mock(side_effect=[ValueError("Error 1"), ValueError("Error 2"), "success"])
        
        # Mock sleep to avoid actual delays
        with mock.patch('time.sleep') as mock_sleep:
            # Call with retry
            result = self.vertex_client._retry_api_call(mock_func)
            
            # Verify result
            self.assertEqual(result, "success")
            
            # Verify function was called three times
            self.assertEqual(mock_func.call_count, 3)
            
            # Verify sleep was called twice with increasing delays
            mock_sleep.assert_has_calls([
                mock.call(1.0),  # Initial delay
                mock.call(2.0),  # Second delay
            ])
    
    def test_retry_api_call_all_fail(self):
        """Test API call that fails all retries."""
        # Mock function that always fails
        error = ValueError("Persistent error")
        mock_func = mock.Mock(side_effect=error)
        
        # Mock sleep to avoid actual delays
        with mock.patch('time.sleep') as mock_sleep:
            # Call with retry should raise the error
            with self.assertRaises(ValueError) as context:
                self.vertex_client._retry_api_call(mock_func)
            
            # Verify the error is the same one
            self.assertEqual(context.exception, error)
            
            # Verify function was called max_retries times
            self.assertEqual(mock_func.call_count, self.vertex_client.max_retries)
            
            # Verify sleep was called (max_retries - 1) times
            self.assertEqual(mock_sleep.call_count, self.vertex_client.max_retries - 1)
    
    @mock.patch('google.generativeai.get_model')
    def test_generate_embeddings_single(self, mock_get_model):
        """Test generating embeddings for a single text."""
        # Mock embedding model
        mock_model = mock.Mock()
        mock_model.supported_generation_methods = ["embeddings"]
        mock_get_model.return_value = mock_model
        
        # Mock embedding result
        mock_embedding = mock.Mock()
        mock_embedding.values = [0.1, 0.2, 0.3]
        mock_result = mock.Mock()
        mock_result.embeddings = [mock_embedding]
        mock_model.embed_content.return_value = mock_result
        
        # Generate embeddings
        embeddings = self.vertex_client.generate_embeddings("Test text")
        
        # Verify get_model was called with correct model name
        mock_get_model.assert_called_once_with("textembedding-gecko@003")
        
        # Verify embed_content was called with correct text
        mock_model.embed_content.assert_called_once_with(content=["Test text"])
        
        # Verify result
        self.assertEqual(embeddings, [0.1, 0.2, 0.3])
    
    @mock.patch('google.generativeai.get_model')
    def test_generate_embeddings_multiple(self, mock_get_model):
        """Test generating embeddings for multiple texts."""
        # Mock embedding model
        mock_model = mock.Mock()
        mock_model.supported_generation_methods = ["embeddings"]
        mock_get_model.return_value = mock_model
        
        # Mock embedding results
        mock_embedding1 = mock.Mock()
        mock_embedding1.values = [0.1, 0.2, 0.3]
        mock_embedding2 = mock.Mock()
        mock_embedding2.values = [0.4, 0.5, 0.6]
        mock_result = mock.Mock()
        mock_result.embeddings = [mock_embedding1, mock_embedding2]
        mock_model.embed_content.return_value = mock_result
        
        # Generate embeddings
        embeddings = self.vertex_client.generate_embeddings(["Text 1", "Text 2"])
        
        # Verify get_model was called with correct model name
        mock_get_model.assert_called_once_with("textembedding-gecko@003")
        
        # Verify embed_content was called with correct texts
        mock_model.embed_content.assert_called_once_with(content=["Text 1", "Text 2"])
        
        # Verify result
        self.assertEqual(embeddings, [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]])
    
    @mock.patch('google.generativeai.get_model')
    def test_generate_embeddings_unsupported_model(self, mock_get_model):
        """Test generating embeddings with unsupported model."""
        # Mock model without embedding support
        mock_model = mock.Mock()
        mock_model.supported_generation_methods = ["generateContent"]
        mock_get_model.return_value = mock_model
        
        # Generate embeddings should raise ValueError
        with self.assertRaises(ValueError):
            self.vertex_client.generate_embeddings("Test text")
    
    @mock.patch('google.generativeai.GenerativeModel')
    def test_generate_text(self, mock_generative_model_class):
        """Test generating text."""
        # Mock generative model
        mock_model = mock.Mock()
        mock_generative_model_class.return_value = mock_model
        
        # Mock response
        mock_response = mock.Mock()
        mock_response.text = "Generated text response"
        mock_model.generate_content.return_value = mock_response
        
        # Generate text
        response = self.vertex_client.generate_text(
            prompt="Test prompt",
            temperature=0.5,
            max_output_tokens=2048,
        )
        
        # Verify GenerativeModel was instantiated with correct model name
        mock_generative_model_class.assert_called_once_with(model_name="gemini-1.5-pro")
        
        # Verify generate_content was called with correct arguments
        mock_model.generate_content.assert_called_once_with(
            "Test prompt",
            generation_config={
                "temperature": 0.5,
                "max_output_tokens": 2048,
                "top_p": 0.95,
                "top_k": 40,
            },
        )
        
        # Verify result
        self.assertEqual(response, "Generated text response")
    
    @mock.patch('google.generativeai.GenerativeModel')
    def test_generate_chat_response(self, mock_generative_model_class):
        """Test generating chat response."""
        # Mock generative model
        mock_model = mock.Mock()
        mock_generative_model_class.return_value = mock_model
        
        # Mock chat
        mock_chat = mock.Mock()
        mock_model.start_chat.return_value = mock_chat
        
        # Mock response
        mock_response = mock.Mock()
        mock_response.text = "Chat response"
        mock_chat.send_message.return_value = mock_response
        
        # Generate chat response
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello, how are you?"},
        ]
        response = self.vertex_client.generate_chat_response(messages)
        
        # Verify GenerativeModel was instantiated with correct model name
        mock_generative_model_class.assert_called_once_with(model_name="gemini-1.5-pro")
        
        # Verify start_chat was called
        mock_model.start_chat.assert_called_once()
        
        # Verify send_message was called with correct content
        mock_chat.send_message.assert_called_once_with(
            "Hello, how are you?",
            generation_config={
                "temperature": 0.2,
                "max_output_tokens": 1024,
                "top_p": 0.95,
                "top_k": 40,
            },
        )
        
        # Verify result
        self.assertEqual(response, "Chat response")
    
    @mock.patch('google.generativeai.GenerativeModel')
    def test_analyze_document(self, mock_generative_model_class):
        """Test document analysis."""
        # Mock the generate_text method
        with mock.patch.object(self.vertex_client, 'generate_text') as mock_generate_text:
            # Set up mock return value
            mock_generate_text.return_value = "Analysis result"
            
            # Analyze document
            result = self.vertex_client.analyze_document(
                document_text="Document content",
                task="Summarize the document",
                temperature=0.3,
            )
            
            # Verify generate_text was called with correct arguments
            expected_prompt = """Task: Summarize the document

Document:
Document content

Analysis:"""
            mock_generate_text.assert_called_once_with(
                prompt=expected_prompt,
                model="gemini-1.5-pro",
                temperature=0.3,
                max_output_tokens=4096,
            )
            
            # Verify result
            self.assertEqual(result, "Analysis result")
    
    @mock.patch('google.generativeai.GenerativeModel')
    def test_extract_entities(self, mock_generative_model_class):
        """Test entity extraction."""
        # Mock the generate_text method
        with mock.patch.object(self.vertex_client, 'generate_text') as mock_generate_text:
            # Set up mock return value with JSON
            mock_generate_text.return_value = """Here are the extracted entities:

```json
{
  "Person": [
    {"text": "John Doe", "start": 10, "end": 18},
    {"text": "Jane Smith", "start": 42, "end": 52}
  ],
  "Organization": [
    {"text": "Acme Corp", "start": 65, "end": 74}
  ]
}
```"""
            
            # Extract entities
            entities = self.vertex_client.extract_entities(
                document_text="Document mentioning John Doe and Jane Smith from Acme Corp.",
                entity_types=["Person", "Organization", "Date"],
            )
            
            # Verify generate_text was called with correct arguments
            expected_prompt = """Extract the following entity types from the document: Person, Organization, Date

Format the output as a JSON object with entity types as keys and arrays of extracted entities as values.
For each entity, include the text, start position, end position, and any relevant attributes.

Document:
Document mentioning John Doe and Jane Smith from Acme Corp.

Extracted Entities (JSON format):"""
            mock_generate_text.assert_called_once_with(
                prompt=expected_prompt,
                model="gemini-1.5-pro",
                temperature=0.1,
                max_output_tokens=4096,
            )
            
            # Verify result
            expected_entities = {
                "Person": [
                    {"text": "John Doe", "start": 10, "end": 18},
                    {"text": "Jane Smith", "start": 42, "end": 52}
                ],
                "Organization": [
                    {"text": "Acme Corp", "start": 65, "end": 74}
                ]
            }
            self.assertEqual(entities, expected_entities)
    
    @mock.patch('google.generativeai.GenerativeModel')
    def test_extract_entities_invalid_json(self, mock_generative_model_class):
        """Test entity extraction with invalid JSON response."""
        # Mock the generate_text method
        with mock.patch.object(self.vertex_client, 'generate_text') as mock_generate_text:
            # Set up mock return value with invalid JSON
            mock_generate_text.return_value = "Here are the extracted entities: No JSON found"
            
            # Extract entities
            entities = self.vertex_client.extract_entities(
                document_text="Test document",
                entity_types=["Person"],
            )
            
            # Verify result is empty dict
            self.assertEqual(entities, {})


if __name__ == "__main__":
    unittest.main()
