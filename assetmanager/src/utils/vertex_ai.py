"""
Utility functions for interacting with Google Cloud Vertex AI models.
"""
from typing import Dict, List, Optional, Union

import google.cloud.aiplatform as aiplatform
from google.cloud.aiplatform.gapic.schema import predict
from vertexai.generative_models import GenerationConfig, GenerativeModel, Part
from vertexai.language_models import TextEmbeddingModel

from src.utils.config import GCP_LOCATION, GCP_PROJECT, LLM_MODEL, EMBEDDING_MODEL


def init_vertex_ai():
    """Initialize the Vertex AI SDK."""
    aiplatform.init(project=GCP_PROJECT, location=GCP_LOCATION)


def get_text_embedding(text: str, model_name: str = EMBEDDING_MODEL) -> List[float]:
    """
    Get embedding vector for a text using Vertex AI embedding model.
    
    Args:
        text: The text to embed
        model_name: The embedding model to use (defaults to latest Gemini model)
        
    Returns:
        List[float]: The embedding vector
    """
    init_vertex_ai()
    model = TextEmbeddingModel.from_pretrained(model_name)
    embeddings = model.get_embeddings([text])
    
    if not embeddings or not embeddings[0].values:
        raise ValueError(f"Failed to get embeddings for text: {text[:100]}...")
        
    return embeddings[0].values


def generate_text(
    prompt: str,
    temperature: float = 0.2,
    max_output_tokens: int = 1024,
    top_k: int = 40,
    top_p: float = 0.8,
    model_name: str = LLM_MODEL,
) -> str:
    """
    Generate text using Vertex AI Gemini model.
    
    Args:
        prompt: The prompt to generate from
        temperature: Temperature for generation (higher is more creative)
        max_output_tokens: Maximum tokens to generate
        top_k: Top-k for sampling
        top_p: Top-p for sampling
        model_name: The model to use (defaults to latest Gemini Pro model)
        
    Returns:
        str: The generated text
    """
    init_vertex_ai()
    model = GenerativeModel(model_name)
    generation_config = GenerationConfig(
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        top_k=top_k,
        top_p=top_p,
    )
    
    response = model.generate_content(
        prompt,
        generation_config=generation_config,
    )
    
    return response.text


def process_multipart_content(
    text_prompt: str,
    image_parts: Optional[List[str]] = None,
    temperature: float = 0.2,
    max_output_tokens: int = 1024,
    top_k: int = 40,
    top_p: float = 0.8,
    model_name: str = LLM_MODEL,
) -> str:
    """
    Process content with both text and optional images using Vertex AI Gemini model.
    
    Args:
        text_prompt: The text prompt
        image_parts: Optional list of image file paths to include
        temperature: Temperature for generation
        max_output_tokens: Maximum tokens to generate
        top_k: Top-k for sampling
        top_p: Top-p for sampling
        model_name: The model to use (defaults to latest Gemini Pro model)
        
    Returns:
        str: The generated response
    """
    init_vertex_ai()
    model = GenerativeModel(model_name)
    generation_config = GenerationConfig(
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        top_k=top_k,
        top_p=top_p,
    )
    
    # Create multipart content
    content_parts = [text_prompt]
    
    # Add images if provided
    if image_parts:
        for image_path in image_parts:
            content_parts.append(Part.from_image(image_path))
    
    response = model.generate_content(
        content_parts,
        generation_config=generation_config,
    )
    
    return response.text


def extract_entities_from_text(
    text: str,
    extraction_prompt: str,
    temperature: float = 0.0,  # Use low/zero temperature for deterministic extraction
    max_output_tokens: int = 2048,
    model_name: str = LLM_MODEL,
) -> str:
    """
    Extract structured information from text using Gemini.
    
    Args:
        text: The text to extract from
        extraction_prompt: The prompt template for extraction
        temperature: Temperature for generation
        max_output_tokens: Maximum tokens to generate
        model_name: The model to use
        
    Returns:
        str: The extracted information in the requested format
    """
    # Replace placeholder in prompt template with actual text
    full_prompt = extraction_prompt.replace("$ctext", text)
    
    # Call Gemini with structured extraction prompt
    return generate_text(
        prompt=full_prompt,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        model_name=model_name,
    )
