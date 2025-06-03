#!/usr/bin/env python
"""
Vertex AI utilities for the Neo4j Generative AI Google Cloud project.

This module provides functionality for interacting with Google Vertex AI,
including embedding generation and LLM interactions using Gemini models.
"""

import os
import logging
import time
from typing import Dict, List, Any, Optional, Union, Tuple

import google.generativeai as genai
from google.api_core import retry
from vertexai.preview.generative_models import GenerativeModel, Part, Content, GenerationConfig

from . import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class VertexAIClient:
    """Client for interacting with Google Vertex AI services."""
    
    def __init__(
        self,
        project_id: Optional[str] = None,
        location: Optional[str] = None,
        model_name: Optional[str] = None,
        embedding_model: Optional[str] = None,
        max_retries: int = 3,
        initial_retry_delay: float = 1.0,
        retry_multiplier: float = 2.0,
        max_retry_delay: float = 60.0,
    ):
        """
        Initialize the Vertex AI client.
        
        Args:
            project_id: GCP project ID (defaults to config.GCP_PROJECT_ID)
            location: GCP location (defaults to config.VERTEX_LOCATION)
            model_name: Gemini model name (defaults to config.VERTEX_MODEL)
            embedding_model: Embedding model name (defaults to config.VERTEX_EMBEDDING_MODEL)
            max_retries: Maximum number of retries for API calls
            initial_retry_delay: Initial delay for retry backoff in seconds
            retry_multiplier: Multiplier for retry backoff
            max_retry_delay: Maximum delay for retry backoff in seconds
        """
        self.project_id = project_id or config.GCP_PROJECT_ID
        self.location = location or config.VERTEX_LOCATION
        self.model_name = model_name or config.VERTEX_MODEL
        self.embedding_model = embedding_model or config.VERTEX_EMBEDDING_MODEL
        
        if not self.project_id or not self.location:
            raise ValueError("GCP_PROJECT_ID and VERTEX_LOCATION must be set in environment or provided")
        
        # Retry configuration
        self.max_retries = max_retries
        self.initial_retry_delay = initial_retry_delay
        self.retry_multiplier = retry_multiplier
        self.max_retry_delay = max_retry_delay
        
        # Initialize Vertex AI
        self._init_vertex_ai()
        
        logger.info(f"Initialized VertexAIClient with project_id={self.project_id}, location={self.location}")
    
    def _init_vertex_ai(self) -> None:
        """
        Initialize Vertex AI client.
        """
        # Configure google-genai SDK
        genai.configure(
            project_id=self.project_id,
            location=self.location,
        )
    
    def _exponential_backoff(self, attempt: int) -> float:
        """
        Calculate exponential backoff delay.
        
        Args:
            attempt: Current attempt number (0-based)
            
        Returns:
            Delay in seconds
        """
        delay = min(
            self.max_retry_delay,
            self.initial_retry_delay * (self.retry_multiplier ** attempt)
        )
        return delay
    
    def _retry_api_call(self, func, *args, **kwargs):
        """
        Retry an API call with exponential backoff.
        
        Args:
            func: Function to call
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            Exception: If all retries fail
        """
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                logger.warning(f"API call failed (attempt {attempt+1}/{self.max_retries}): {e}")
                
                if attempt < self.max_retries - 1:
                    delay = self._exponential_backoff(attempt)
                    logger.info(f"Retrying in {delay:.2f} seconds...")
                    time.sleep(delay)
                else:
                    logger.error(f"API call failed after {self.max_retries} attempts: {e}")
        
        raise last_exception
    
    def generate_embeddings(
        self,
        texts: Union[str, List[str]],
        model: Optional[str] = None,
    ) -> Union[List[float], List[List[float]]]:
        """
        Generate embeddings for text using Vertex AI.
        
        Args:
            texts: Text or list of texts to embed
            model: Embedding model name (defaults to self.embedding_model)
            
        Returns:
            Embeddings as list of floats or list of list of floats
        """
        model_name = model or self.embedding_model
        
        if not model_name:
            raise ValueError("Embedding model name must be provided")
        
        # Get embedding model
        embedding_model = genai.get_model(model_name)
        
        # Check if model supports embeddings
        if "embeddings" not in embedding_model.supported_generation_methods:
            raise ValueError(f"Model {model_name} does not support embeddings")
        
        # Generate embeddings
        logger.info(f"Generating embeddings using model {model_name}")
        
        # Handle single text or list of texts
        single_input = isinstance(texts, str)
        input_texts = [texts] if single_input else texts
        
        try:
            # Call API with retry
            result = self._retry_api_call(
                embedding_model.embed_content,
                content=input_texts,
            )
            
            # Extract embeddings
            embeddings = [embedding.values for embedding in result.embeddings]
            
            # Return single embedding or list of embeddings
            if single_input:
                return embeddings[0]
            else:
                return embeddings
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            raise
    
    def generate_text(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_output_tokens: int = 1024,
        top_p: float = 0.95,
        top_k: int = 40,
    ) -> str:
        """
        Generate text using Vertex AI Gemini model.
        
        Args:
            prompt: Text prompt
            model: Model name (defaults to self.model_name)
            temperature: Temperature for sampling (0.0-1.0)
            max_output_tokens: Maximum number of tokens to generate
            top_p: Top-p sampling parameter (0.0-1.0)
            top_k: Top-k sampling parameter
            
        Returns:
            Generated text
        """
        model_name = model or self.model_name
        
        if not model_name:
            raise ValueError("Model name must be provided")
        
        # Get generative model
        generative_model = genai.GenerativeModel(model_name=model_name)
        
        # Set generation config
        generation_config = {
            "temperature": temperature,
            "max_output_tokens": max_output_tokens,
            "top_p": top_p,
            "top_k": top_k,
        }
        
        logger.info(f"Generating text using model {model_name}")
        
        try:
            # Call API with retry
            response = self._retry_api_call(
                generative_model.generate_content,
                prompt,
                generation_config=generation_config,
            )
            
            # Extract text
            return response.text
        except Exception as e:
            logger.error(f"Failed to generate text: {e}")
            raise
    
    def generate_chat_response(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_output_tokens: int = 1024,
        top_p: float = 0.95,
        top_k: int = 40,
    ) -> str:
        """
        Generate a chat response using Vertex AI Gemini model.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content' keys
            model: Model name (defaults to self.model_name)
            temperature: Temperature for sampling (0.0-1.0)
            max_output_tokens: Maximum number of tokens to generate
            top_p: Top-p sampling parameter (0.0-1.0)
            top_k: Top-k sampling parameter
            
        Returns:
            Generated response text
        """
        model_name = model or self.model_name
        
        if not model_name:
            raise ValueError("Model name must be provided")
        
        # Get generative model
        generative_model = genai.GenerativeModel(model_name=model_name)
        
        # Set generation config
        generation_config = {
            "temperature": temperature,
            "max_output_tokens": max_output_tokens,
            "top_p": top_p,
            "top_k": top_k,
        }
        
        # Format messages for the API
        chat = generative_model.start_chat()
        
        logger.info(f"Generating chat response using model {model_name}")
        
        try:
            # Send all messages to the chat
            for message in messages:
                role = message.get("role", "user").lower()
                content = message.get("content", "")
                
                if role == "user":
                    # Call API with retry for user messages
                    response = self._retry_api_call(
                        chat.send_message,
                        content,
                        generation_config=generation_config,
                    )
                elif role == "system":
                    # System messages are handled differently
                    # We'll prepend them to the first user message
                    continue
            
            # Extract text from the final response
            return response.text
        except Exception as e:
            logger.error(f"Failed to generate chat response: {e}")
            raise
    
    def analyze_document(
        self,
        document_text: str,
        task: str,
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_output_tokens: int = 4096,
    ) -> str:
        """
        Analyze a document using Vertex AI Gemini model.
        
        Args:
            document_text: Document text to analyze
            task: Description of the analysis task
            model: Model name (defaults to self.model_name)
            temperature: Temperature for sampling (0.0-1.0)
            max_output_tokens: Maximum number of tokens to generate
            
        Returns:
            Analysis result
        """
        model_name = model or self.model_name
        
        if not model_name:
            raise ValueError("Model name must be provided")
        
        # Create prompt
        prompt = f"""Task: {task}

Document:
{document_text}

Analysis:"""
        
        # Generate text
        return self.generate_text(
            prompt=prompt,
            model=model_name,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
    
    def extract_entities(
        self,
        document_text: str,
        entity_types: List[str],
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_output_tokens: int = 4096,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Extract entities from a document using Vertex AI Gemini model.
        
        Args:
            document_text: Document text to analyze
            entity_types: List of entity types to extract (e.g., ["Person", "Organization", "Date"])
            model: Model name (defaults to self.model_name)
            temperature: Temperature for sampling (0.0-1.0)
            max_output_tokens: Maximum number of tokens to generate
            
        Returns:
            Dictionary mapping entity types to lists of extracted entities
        """
        model_name = model or self.model_name
        
        if not model_name:
            raise ValueError("Model name must be provided")
        
        # Create prompt
        entity_types_str = ", ".join(entity_types)
        prompt = f"""Extract the following entity types from the document: {entity_types_str}

Format the output as a JSON object with entity types as keys and arrays of extracted entities as values.
For each entity, include the text, start position, end position, and any relevant attributes.

Document:
{document_text}

Extracted Entities (JSON format):"""
        
        # Generate text
        response = self.generate_text(
            prompt=prompt,
            model=model_name,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
        
        # Parse JSON response
        try:
            import json
            # Find JSON in the response
            json_start = response.find('{')
            json_end = response.rfind('}')
            
            if json_start >= 0 and json_end >= 0:
                json_str = response[json_start:json_end+1]
                entities = json.loads(json_str)
                return entities
            else:
                logger.warning(f"Failed to parse JSON from response: {response}")
                return {}
        except Exception as e:
            logger.error(f"Failed to parse extracted entities: {e}")
            return {}
