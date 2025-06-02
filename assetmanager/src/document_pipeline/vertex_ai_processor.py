"""
Vertex AI Processor module for interacting with Google Cloud Vertex AI services.

This module provides functionality for:
- Generating text embeddings using models like 'text-embedding-004'.
- Interacting with Large Language Models (LLMs) like Gemini for tasks such as 
  advanced entity extraction, summarization, and question answering.
"""
import logging
from typing import List, Dict, Any, Optional

from google import genai
from google.genai import types as genai_types

logger = logging.getLogger(__name__)

class VertexAIProcessor:
    """
    Handles interactions with Google Cloud Vertex AI for embeddings and LLM tasks.
    """

    def __init__(
        self,
        project_id: str,
        location: str = "us-central1",
        default_embedding_model: str = "text-embedding-004",
        default_llm_model: str = "gemini-2.5-pro-preview-05-06", # Updated as per user preference # Using a generally available powerful model
    ):
        """
        Initialize the VertexAIProcessor.

        Args:
            project_id: Google Cloud project ID.
            location: Google Cloud region for Vertex AI services.
            default_embedding_model: Default model name for text embeddings.
            default_llm_model: Default model name for LLM interactions.
        """
        self.project_id = project_id
        self.location = location
        self.default_embedding_model = default_embedding_model
        self.default_llm_model = default_llm_model

        # Configure GenAI SDK for Vertex AI
        try:
            genai.configure(vertexai=True, project=project_id, location=location)
            self.client = genai.Client(vertexai=True, project=project_id, location=location)
            logger.info(f"Vertex AI Processor initialized for project {project_id} in {location}.")
        except Exception as e:
            logger.error(f"Failed to initialize GenAI SDK for Vertex AI: {e}", exc_info=True)
            raise

    def get_text_embeddings(
        self, 
        texts: List[str], 
        model_name: Optional[str] = None,
        task_type: str = "RETRIEVAL_DOCUMENT",
        title: Optional[str] = None
    ) -> List[List[float]]:
        """
        Generate embedding vectors for a list of texts.

        Args:
            texts: A list of strings to embed.
            model_name: The embedding model to use. If None, uses default_embedding_model.
            task_type: The task type for the embedding. Common types include:
                       "RETRIEVAL_QUERY", "RETRIEVAL_DOCUMENT", "SEMANTIC_SIMILARITY",
                       "CLASSIFICATION", "CLUSTERING".
            title: Optional title for the content, can improve document embeddings.

        Returns:
            List[List[float]]: A list of embedding vectors, one for each input text.
        """
        active_model = model_name or self.default_embedding_model
        logger.info(f"Generating embeddings for {len(texts)} texts using model {active_model}.")
        
        try:
            # The genai SDK's embed_content can take a list of strings directly
            # or a list of genai_types.ContentPart objects.
            # For batching with specific parameters like task_type and title, 
            # it's often better to iterate if the API doesn't directly support batching these params,
            # or construct a more complex request if it does. The current SDK simplifies this.
            
            # The `embed_content` method in the latest google-genai SDK handles batching implicitly.
            # However, if you need to pass `task_type` or `title` per item, you might need to loop.
            # For a general case where task_type and title apply to all texts in the batch:
            
            response = self.client.models.embed_content(
                model=active_model,
                content=texts, # Pass the list of texts directly
                task_type=task_type,
                title=title # Title applies to all texts if provided here
            )
            
            if not response or not response.embedding:
                 # If response.embedding is a list of embeddings:
                if isinstance(response.embedding, list) and all(isinstance(e, list) for e in response.embedding):
                    return response.embedding
                else: # Fallback for single text or unexpected structure
                    logger.warning("Embeddings response structure not as expected for batch, attempting individual processing.")
                    # This part is a fallback, ideally the batch call works directly
                    embeddings = []
                    for text_item in texts:
                        item_response = self.client.models.embed_content(
                            model=active_model, 
                            content=text_item, 
                            task_type=task_type, 
                            title=title
                        )
                        if item_response and item_response.embedding:
                            embeddings.append(item_response.embedding)
                        else:
                            logger.error(f"Failed to get embedding for text: {text_item[:100]}...")
                            embeddings.append([]) # Or handle error appropriately
                    return embeddings

            return response.embedding # Assuming this is List[List[float]]

        except Exception as e:
            logger.error(f"Error generating text embeddings: {e}", exc_info=True)
            # Return empty embeddings for all texts in case of a batch error
            return [[] for _ in texts]

    def generate_text_from_prompt(
        self,
        prompt: str,
        model_name: Optional[str] = None,
        temperature: float = 0.5,
        max_output_tokens: int = 2048,
        top_k: int = 40,
        top_p: float = 0.95,
        system_instruction: Optional[str] = None
    ) -> str:
        """
        Generate text using an LLM based on a given prompt.

        Args:
            prompt: The input prompt for the LLM.
            model_name: The LLM model to use. If None, uses default_llm_model.
            temperature: Controls randomness. Lower is more deterministic.
            max_output_tokens: Maximum number of tokens to generate.
            top_k: Top-k sampling parameter.
            top_p: Top-p (nucleus) sampling parameter.
            system_instruction: Optional system-level instruction for the model.

        Returns:
            str: The generated text.
        """
        active_model = model_name or self.default_llm_model
        logger.info(f"Generating text using model {active_model} with prompt: {prompt[:100]}...")

        try:
            model_instance = self.client.generative_models.get_model(active_model)
            
            generation_config = genai_types.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                top_k=top_k,
                top_p=top_p
            )
            
            contents = [prompt]
            safety_settings = [
                 genai_types.SafetySetting(category=cat, threshold=genai_types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE) 
                 for cat in genai_types.HarmCategory
            ]

            request_args = {
                "contents": contents,
                "generation_config": generation_config,
                "safety_settings": safety_settings
            }

            if system_instruction:
                # For newer models that support system_instruction directly in generate_content
                if hasattr(model_instance, 'system_instruction'): # Check if model object supports it
                     request_args["system_instruction"] = genai_types.Content(parts=[genai_types.Part.from_text(system_instruction)])
                else: # Fallback for models that take it as part of the prompt or different structure
                    logger.warning(f"Model {active_model} might not directly support system_instruction in generate_content. Prepending to prompt or ignoring.")
                    # For some models, system instructions are prepended or handled differently.
                    # This example assumes direct support or graceful degradation.

            response = model_instance.generate_content(**request_args)
            
            if response and response.candidates and response.candidates[0].content.parts:
                return response.candidates[0].content.parts[0].text
            else:
                logger.warning("No content generated or unexpected response structure.")
                return ""
        except Exception as e:
            logger.error(f"Error generating text: {e}", exc_info=True)
            return ""

    def extract_structured_data_from_text(
        self,
        text_content: str,
        json_schema: Dict[str, Any],
        model_name: Optional[str] = None,
        prompt_template: Optional[str] = None, # Optional custom prompt template
        temperature: float = 0.1 # Lower temperature for more deterministic extraction
    ) -> Optional[Dict[str, Any]]:
        """
        Extracts structured data from text according to a JSON schema using an LLM.

        Args:
            text_content: The text from which to extract data.
            json_schema: A dictionary representing the JSON schema for the desired output.
            model_name: The LLM model to use. If None, uses default_llm_model.
            prompt_template: An optional f-string template for the prompt. 
                             Must include {text_content} and {json_schema} placeholders.
            temperature: Controls randomness for generation.

        Returns:
            Optional[Dict[str, Any]]: A dictionary with the extracted data, or None if extraction fails.
        """
        active_model = model_name or self.default_llm_model
        logger.info(f"Extracting structured data using model {active_model}.")

        if prompt_template:
            prompt = prompt_template.format(text_content=text_content, json_schema=str(json_schema))
        else:
            prompt = (
                f"Extract information from the following text according to this JSON schema:\n"
                f"Schema:\n{json_schema}\n\n"
                f"Text:\n{text_content}\n\n"
                f"Ensure the output is a valid JSON object matching the schema."
            )
        
        try:
            model_instance = self.client.generative_models.get_model(active_model)
            
            # For models supporting direct JSON mode / schema enforcement:
            generation_config = genai_types.GenerationConfig(
                temperature=temperature,
                response_mime_type="application/json", # Request JSON output
                response_schema=json_schema # Provide the schema for enforcement
            )

            response = model_instance.generate_content(
                contents=[prompt],
                generation_config=generation_config
            )

            if response and response.candidates and response.candidates[0].content.parts:
                # The response part should be JSON text, parse it
                json_response_text = response.candidates[0].content.parts[0].text
                return json.loads(json_response_text) # json module from standard library
            else:
                logger.warning("No structured data extracted or unexpected response structure.")
                return None
        except Exception as e:
            logger.error(f"Error extracting structured data: {e}", exc_info=True)
            import json # Ensure json is imported for the except block if not already
            return None

# Example Usage (for testing or demonstration)
if __name__ == '__main__':
    # This example assumes you have a GCP project set up and Vertex AI API enabled.
    # You would also need to authenticate, e.g., by running `gcloud auth application-default login`
    
    import os
    import json # Make sure json is imported for the main block

    PROJECT_ID = os.getenv("GCP_PROJECT_ID") # Ensure this env var is set
    if not PROJECT_ID:
        print("Please set the GCP_PROJECT_ID environment variable.")
    else:
        print(f"Initializing VertexAIProcessor for project {PROJECT_ID}...")
        vertex_processor = VertexAIProcessor(project_id=PROJECT_ID)

        # 1. Test Text Embedding
        print("\n--- Testing Text Embedding ---")
        sample_texts = [
            "The quick brown fox jumps over the lazy dog.",
            "Artificial intelligence is rapidly changing the world."
        ]
        embeddings = vertex_processor.get_text_embeddings(sample_texts)
        if embeddings and len(embeddings) == len(sample_texts) and all(e for e in embeddings):
            print(f"Successfully generated {len(embeddings)} embeddings.")
            print(f"Dimension of first embedding: {len(embeddings[0])}")
        else:
            print("Failed to generate embeddings or embeddings are empty.")

        # 2. Test Text Generation
        print("\n--- Testing Text Generation ---")
        generation_prompt = "What is the capital of France?"
        generated_text = vertex_processor.generate_text_from_prompt(generation_prompt)
        if generated_text:
            print(f"Prompt: {generation_prompt}")
            print(f"Generated Text: {generated_text}")
        else:
            print("Failed to generate text.")

        # 3. Test Structured Data Extraction
        print("\n--- Testing Structured Data Extraction ---")
        extraction_text = "John Doe is a software engineer at Example Corp. He lives in New York and his email is john.doe@example.com."
        extraction_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "title": {"type": "string"},
                "company": {"type": "string"},
                "city": {"type": "string"},
                "email": {"type": "string"}
            },
            "required": ["name", "email"]
        }
        extracted_data = vertex_processor.extract_structured_data_from_text(extraction_text, extraction_schema)
        if extracted_data:
            print(f"Original Text: {extraction_text}")
            print(f"Extraction Schema: {json.dumps(extraction_schema, indent=2)}")
            print(f"Extracted Data: {json.dumps(extracted_data, indent=2)}")
        else:
            print("Failed to extract structured data.")
