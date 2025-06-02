"""
Utility functions for interacting with Google Gen AI SDK and Gemini models.
This module replaces the older vertex_ai.py to use the new unified Google GenAI SDK.
"""
import os
from typing import Dict, List, Optional, Union, Any

from google import genai
from google.genai import types
from google.generativeai.types import GenerationConfig # Ensure GenerationConfig is imported

from src.utils.config import get_gcp_settings

# Load settings from config.py which handles .env loading
_gcp_settings = get_gcp_settings()
GEMINI_LLM_MODEL = _gcp_settings.get("llm_model", "gemini-2.5-flash-preview-05-20")
GEMINI_EMBEDDING_MODEL = _gcp_settings.get("embedding_model", "text-embedding-004")
LLM_THINKING_BUDGET_CONFIG = _gcp_settings.get("llm_thinking_budget", 1024)

def init_genai(project_id: str, location: str = "us-central1"):
    """
    Initialize the Google GenAI SDK for Vertex AI.
    
    Args:
        project_id: Google Cloud project ID
        location: Google Cloud region
    """
    # Configuration for Vertex AI is typically handled by ADC or GOOGLE_APPLICATION_CREDENTIALS
    # and by passing project/location to the Client or GenerativeModel constructor.
    # The genai.configure() method with these parameters is not standard for Vertex AI.
    pass


def get_client(project_id: str, location: str = "us-central1") -> genai.Client:
    """
    Get a Google GenAI client configured for Vertex AI.
    
    Args:
        project_id: Google Cloud project ID
        location: Google Cloud region
        
    Returns:
        A configured GenAI client
    """
    return genai.Client(vertexai=True, project=project_id, location=location)


def get_text_embedding(
    text: str, 
    model_name: str = GEMINI_EMBEDDING_MODEL,
    project_id: str = None,
    location: str = "us-central1"
) -> List[float]:
    """
    Get embedding vector for a text using the Gemini embedding model.
    
    Args:
        text: The text to embed
        model_name: The embedding model to use
        project_id: Google Cloud project ID (required if not initialized)
        location: Google Cloud region
        
    Returns:
        List[float]: The embedding vector
    """
    client = get_client(project_id, location) if project_id else genai.Client()
    
    response = client.models.embed_content(
        model=model_name,
        content=text
    )
    
    if not response or not response.embedding:
        raise ValueError(f"Failed to get embeddings for text: {text[:100]}...")
        
    return response.embedding


def generate_text(
    prompt: str,
    temperature: float = 0.2,
    max_output_tokens: int = 1024,
    top_k: int = 40,
    top_p: float = 0.8,
    model_name: str = GEMINI_LLM_MODEL,
    project_id: str = None,
    location: str = "us-central1",
    system_instruction: str = None,
    enable_thinking: bool = True,
    thinking_budget_override: Optional[int] = None,
) -> str:
    """
    Generate text using Gemini model with the new Google GenAI SDK.
    
    Args:
        prompt: The prompt to generate from
        temperature: Temperature for generation (higher is more creative)
        max_output_tokens: Maximum tokens to generate
        top_k: Top-k for sampling
        top_p: Top-p for sampling
        model_name: The model to use
        project_id: Google Cloud project ID (required if not initialized)
        location: Google Cloud region
        system_instruction: Optional system instruction for the model
        enable_thinking: Whether to enable the thinking mode (Gemini 2.5+ only)
        
    Returns:
        str: The generated text
    """
    client = get_client(project_id, location) if project_id else genai.Client()
    
    current_thinking_budget = thinking_budget_override if thinking_budget_override is not None else LLM_THINKING_BUDGET_CONFIG

    gen_config_params = {
        "temperature": temperature,
        "max_output_tokens": max_output_tokens,
        "top_k": top_k,
        "top_p": top_p,
    }

    # Add thinking_config if enabled and model supports it (e.g., flash models)
    # The documentation indicates thinking_budget is only for gemini-2.5-flash
    if enable_thinking and "flash" in model_name.lower() and current_thinking_budget > 0:
        thinking_config = types.ThinkingConfig(thinking_budget=current_thinking_budget)
        gen_config_params["thinking_config"] = thinking_config
    elif enable_thinking and "flash" in model_name.lower() and current_thinking_budget == 0:
        # Explicitly disable thinking if budget is 0 for flash models
        thinking_config = types.ThinkingConfig(thinking_budget=0)
        gen_config_params["thinking_config"] = thinking_config

    generation_config = types.GenerationConfig(**gen_config_params)

    contents_to_send = [prompt]
    # System instruction handling: For client.models.generate_content, it's often part of the 'contents' list
    # or by using GenerativeModel(model_name, system_instruction=...) and then model.generate_content.
    # If a system_instruction is provided, we might need to adjust how 'contents' is structured
    # or switch to using GenerativeModel.
    # For now, let's assume simple prompt for 'contents'.
    # If system_instruction is critical, this part needs refinement.
    # Example: contents = [system_instruction, prompt] or using specific roles.

    default_safety_settings = [
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
            threshold=types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
        ),
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
            threshold=types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
        ),
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
            threshold=types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
        ),
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
            threshold=types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
        )
    ]

    response = client.models.generate_content(
        model=model_name, # Pass model name directly here
        contents=contents_to_send,
        generation_config=generation_config,
        safety_settings=default_safety_settings
    )

    if not response or not response.candidates:
        raise ValueError(f"Failed to generate text for prompt: {prompt[:100]}...")

    # Add thought token count to logging or return if needed
    # print("Thoughts tokens:",response.usage_metadata.thoughts_token_count)
    # print("Output tokens:",response.usage_metadata.candidates_token_count)

    return response.text


def process_multimodal(
    prompt: str,
    image_path: str,
    temperature: float = 0.2,
    max_output_tokens: int = 1024,
    top_k: int = 40,
    top_p: float = 0.8,
    model_name: str = GEMINI_LLM_MODEL,
    project_id: str = None,
    location: str = "us-central1",
) -> str:
    """
    Process multimodal content (text + image) using Gemini model.
    
    Args:
        prompt: The text prompt
        image_path: Path to the image file
        temperature: Temperature for generation
        max_output_tokens: Maximum tokens to generate
        top_k: Top-k for sampling
        top_p: Top-p for sampling
        model_name: The model to use
        project_id: Google Cloud project ID (required if not initialized)
        location: Google Cloud region
        
    Returns:
        str: The generated response
    """
    client = get_client(project_id, location) if project_id else genai.Client()
    
    generation_config = types.GenerationConfig(
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        top_k=top_k,
        top_p=top_p,
    )
    
    # Create multipart content
    image_part = types.Part.from_file(image_path)
    text_part = types.Part.from_text(prompt)
    
    response = client.models.generate_content(
        model=model_name,
        contents=[text_part, image_part],
        generation_config=generation_config,
    )
    
    return response.text


def extract_structured_data(
    text: str,
    schema: Dict[str, Any],
    temperature: float = 0.0,  # Use low temperature for deterministic extraction
    max_output_tokens: int = 2048,
    model_name: str = GEMINI_LLM_MODEL,
    project_id: str = None,
    location: str = "us-central1",
) -> Dict[str, Any]:
    """
    Extract structured data from text using Gemini model with JSON output.
    
    Args:
        text: The text to extract data from
        schema: The JSON schema for structured extraction
        temperature: Temperature for generation
        max_output_tokens: Maximum tokens to generate
        model_name: The model to use
        project_id: Google Cloud project ID (required if not initialized)
        location: Google Cloud region
        
    Returns:
        Dict[str, Any]: The extracted structured data
    """
    client = get_client(project_id, location) if project_id else genai.Client()
    
    generation_config = types.GenerationConfig(
        temperature=temperature,
        max_output_tokens=max_output_tokens,
    )
    
    # Create a prompt for structured extraction
    prompt = f"""
    Extract the following information from the text below according to the specified schema.
    Only extract information that is explicitly stated in the text.
    
    Text:
    {text}
    """
    
    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
        generation_config=generation_config,
        response_schema=schema,
        response_mime_type="application/json"
    )
    
    return response.json()
